import re

from scoring import check_documentation_quality, extract_score_from_response
from DependencyChecker import check_dependencies_for_repo_with_local_files


def get_file_type(file_path, pipeline_type=None):
    """Determine the type of file for appropriate analysis.

    Uses the PipelineAnalyzer for the given *pipeline_type* (defaults to
    ``"nextflow"``) to classify files via ``get_file_role``.
    """
    from pipeline_analyzers import get_analyzer
    analyzer = get_analyzer(pipeline_type or "nextflow")
    role = analyzer.get_file_role(file_path)
    if role == "code":
        return pipeline_type or "nextflow"
    elif role == "config":
        return "config"
    elif role == "doc":
        return "readme"
    return "generic"


def _analyze_files(repo_dir, files_to_check, pipeline_type, ai_usage, add_to_report):
    """Analyze each file in files_to_check and return a dict of reports."""
    import os
    all_reports = {}

    for file_path in files_to_check:
        add_to_report(f"\n--- Checking {file_path} ---")

        local_file_path = os.path.join(repo_dir, file_path)
        try:
            with open(local_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            add_to_report(f"Could not find {file_path} in repository")
            continue
        except Exception as e:
            add_to_report(f"Error reading {file_path}: {e}")
            continue

        file_type = get_file_type(file_path, pipeline_type)

        if file_type in ("nextflow", "snakemake", "cwl", "wdl"):
            from pipeline_analyzers import get_analyzer
            analyzer = get_analyzer(file_type)
            params = analyzer.extract_params_from_code(content)
            param_docs = dict(re.findall(r'//\s*@param\s+(\w+)\s+(.+)', content))
            add_to_report(f"Found {len(params)} parameters, {len(param_docs)} documented")

            if ai_usage:
                quality_report = check_documentation_quality(content, file_type)
            else:
                quality_report = "Static analysis: file parsed successfully."
            all_reports[file_path] = {
                "type": file_type,
                "params": params,
                "param_docs": param_docs,
                "quality_report": quality_report
            }

        elif file_type == "config":
            if ai_usage:
                quality_report = check_documentation_quality(content, "config")
            else:
                quality_report = "Static analysis: config file present."
            all_reports[file_path] = {
                "type": "config",
                "quality_report": quality_report
            }

        elif file_type == "readme":
            if ai_usage:
                quality_report = check_documentation_quality(content, "readme")
            else:
                quality_report = "Static analysis: documentation file present."
            all_reports[file_path] = {
                "type": "readme",
                "quality_report": quality_report
            }

        add_to_report(f"Successfully analyzed {file_path}")

    return all_reports


def _print_comprehensive_report(all_reports, add_to_report):
    """Print the comprehensive documentation quality report."""
    add_to_report("\n" + "="*60)
    add_to_report("COMPREHENSIVE DOCUMENTATION QUALITY REPORT")
    add_to_report("="*60)

    for file_path, report in all_reports.items():
        add_to_report(f"\n📄 {file_path} ({report['type'].upper()})")
        add_to_report("-" * 40)

        individual_score = extract_score_from_response(report['quality_report'])
        add_to_report(f"📊 Individual Score: {individual_score}/10")

        if report['type'] in ("nextflow", "snakemake", "cwl", "wdl") and report.get('params'):
            add_to_report(f"Parameters found: {len(report['params'])}")
            add_to_report(f"Documented parameters: {len(report['param_docs'])}")
            add_to_report(f"Documentation coverage: {len(report['param_docs'])/len(report['params'])*100:.1f}%")

        add_to_report("\nQuality Analysis:")
        add_to_report(report['quality_report'])


def _check_dependencies(repo_dir, dockerfiles, conda_files, json_output, add_to_report):
    """Check dependency pinning and return score adjustment."""
    add_to_report("\n=== CHECKING DEPENDENCY PINNING ===")
    dependency_report = check_dependencies_for_repo_with_local_files(repo_dir, dockerfiles, conda_files)
    score_adj = 0.0

    if dependency_report:
        add_to_report(dependency_report)
        if "⚠️" not in dependency_report:
            score_adj = 0.5
            add_to_report("\n All dependencies appear to be pinned! Overall score increased by 0.5 point.")
            json_output["dependency_pinning"]["all_pinned"] = True
        else:
            unpinned_deps = []
            for line in dependency_report.split('\n'):
                if line.strip().startswith('- '):
                    unpinned_deps.append(line.strip()[2:])
            json_output["dependency_pinning"]["unpinned_dependencies"] = unpinned_deps

    return score_adj


def _check_param_consistency(repo_dir, files_to_check, param_checking, pipeline_type, json_output, add_to_report):
    """Check parameter consistency and return score adjustment."""
    score_adj = 0.0

    if param_checking:
        from static_checks import run_static_param_check
        add_to_report("\n=== PARAMETER CONSISTENCY CHECK ===")
        param_result = run_static_param_check(repo_dir, files_to_check, pipeline_type=pipeline_type)
        add_to_report(param_result['report'])
        json_output["parameter_consistency"]["checked"] = True
        json_output["parameter_consistency"]["results"] = param_result['report']
        json_output["parameter_consistency"]["details"] = param_result

    # Apply parameter consistency score adjustment
    if json_output["parameter_consistency"]["checked"] and json_output["parameter_consistency"]["results"]:
        param_results = json_output["parameter_consistency"]["results"]
        if "⚠️" in param_results or "❌" in param_results or "inconsistencies found" in param_results.lower() or "MISMATCH" in param_results:
            score_adj = -0.5
            add_to_report(f"\n Parameter consistency issues found! Overall score decreased by 0.5 points.")

    return score_adj


def _assign_badge(overall_score, ai_usage, all_reports, json_output, add_to_report):
    """Assign badge based on score/checks and populate JSON output. Returns (score, badge)."""
    add_to_report("\n" + "="*60)
    add_to_report("OVERALL ASSESSMENT")
    add_to_report("="*60)

    if ai_usage:
        if overall_score >= 8:
            badge = "🥇 Gold"
        elif overall_score >= 6.5:
            badge = "🥈 Silver"
        elif overall_score >= 5:
            badge = "🥉 Bronze"
        else:
            badge = "No Badge"
    else:
        checks_passed = []
        checks_failed = []

        has_docs = any(r['type'] == 'readme' for r in all_reports.values())
        (checks_passed if has_docs else checks_failed).append("Documentation present")

        code_types = {"nextflow", "snakemake", "cwl", "wdl"}
        has_code = any(r['type'] in code_types for r in all_reports.values())
        (checks_passed if has_code else checks_failed).append("Pipeline code present")

        deps_ok = json_output["dependency_pinning"]["all_pinned"]
        (checks_passed if deps_ok else checks_failed).append("Dependencies pinned")

        if json_output["parameter_consistency"]["checked"]:
            param_ok = "MISMATCH" not in json_output["parameter_consistency"].get("results", "")
            (checks_passed if param_ok else checks_failed).append("Parameter consistency")

        passed_all = len(checks_failed) == 0
        badge = "✅ Pass" if passed_all else "❌ Fail"
        overall_score = len(checks_passed) / (len(checks_passed) + len(checks_failed)) * 10

        add_to_report(f"\nChecks passed: {', '.join(checks_passed) or 'none'}")
        if checks_failed:
            add_to_report(f"Checks failed: {', '.join(checks_failed)}")

    # Update JSON data with overall assessment
    json_output["overall_assessment"]["score"] = overall_score
    json_output["overall_assessment"]["medal"] = badge

    # Add individual scores to JSON
    for file_path, report in all_reports.items():
        individual_score = extract_score_from_response(report['quality_report'])
        json_output["overall_assessment"]["individual_scores"][file_path] = {
            "score": individual_score,
            "type": report['type']
        }

        if report['type'] == "config":
            json_output["config_files"]["presence"] = True
            json_output["config_files"]["files_analyzed"].append(file_path)
            json_output["config_files"]["correctness_score"] = individual_score

    add_to_report(f" Overall Score: {overall_score}/10")
    add_to_report(f" Badge: {badge}")
    add_to_report("="*60)

    return overall_score, badge
