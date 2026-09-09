import re

from scoring import check_documentation_quality, extract_score_from_response
from DependencyChecker import inspect_dependencies


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
        except OSError as e:
            raise OSError(f"Cannot read selected file {file_path}: {e}") from e

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

        else:
            raise ValueError(f"Unsupported selected file type: {file_path}")
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

        individual_score = (extract_score_from_response(report['quality_report'])
                            if not report['quality_report'].startswith('Static analysis:') else None)
        add_to_report(f"📊 AI score: {individual_score}/10" if individual_score is not None else "AI score: not requested")

        if report['type'] in ("nextflow", "snakemake", "cwl", "wdl") and report.get('params'):
            add_to_report(f"Parameters found: {len(report['params'])}")
            add_to_report(f"Documented parameters: {len(report['param_docs'])}")
            add_to_report(f"Documentation coverage: {len(report['param_docs'])/len(report['params'])*100:.1f}%")

        add_to_report("\nQuality Analysis:")
        add_to_report(report['quality_report'])


def _check_dependencies(repo_dir, dockerfiles, conda_files, json_output, add_to_report):
    """Use structured dependency evidence, never inferred report wording."""
    result = inspect_dependencies(repo_dir, dockerfiles, conda_files)
    json_output["dependency_pinning"] = result
    add_to_report("\nDependency pinning: " + result["status"])
    for reason in result["reasons"]:
        add_to_report(reason)
    return 0.5 if result["all_pinned"] else 0.0


def _check_param_consistency(repo_dir, files_to_check, param_checking, pipeline_type, json_output, add_to_report):
    if not param_checking:
        return 0.0
    from static_checks import run_static_param_check
    result = run_static_param_check(repo_dir, files_to_check, pipeline_type=pipeline_type)
    json_output["parameter_consistency"] = {
        "checked": True, "status": result["verdict"], "results": result["report"], "details": result,
    }
    add_to_report(result["report"])
    return -0.5 if result["verdict"] == "FAIL" else 0.0


def _assign_badge(overall_score, ai_usage, all_reports, json_output, add_to_report):
    checks = {
        "documentation_present": "PASS" if any(r['type'] == 'readme' for r in all_reports.values()) else "NOT_CHECKED",
        "pipeline_code_present": "PASS" if any(r['type'] in {'nextflow', 'snakemake', 'cwl', 'wdl'} for r in all_reports.values()) else "NOT_CHECKED",
        "dependency_pinning": json_output["dependency_pinning"]["status"],
    }
    if json_output["parameter_consistency"]["checked"]:
        checks["parameter_consistency"] = json_output["parameter_consistency"]["status"]
    status = next((v for v in ("ERROR", "FAIL", "NOT_CHECKED") if v in checks.values()), "PASS")
    if ai_usage:
        badge = "🥇 Gold" if overall_score >= 8 else "🥈 Silver" if overall_score >= 6.5 else "🥉 Bronze" if overall_score >= 5 else "No Badge"
    else:
        overall_score = None
        badge = {"PASS": "✅ Pass", "FAIL": "❌ Fail", "NOT_CHECKED": "Incomplete", "ERROR": "Error"}[status]
    assessment = json_output["overall_assessment"]
    assessment.update(score=overall_score, medal=badge, status=status, checks=checks)
    for path, report in all_reports.items():
        score = extract_score_from_response(report['quality_report']) if ai_usage else None
        assessment["individual_scores"][path] = {"score": score, "type": report['type']}
        if report['type'] == 'config':
            json_output['config_files']['presence'] = True
            json_output['config_files']['files_analyzed'].append(path)
            json_output['config_files']['correctness_score'] = score
    add_to_report(f"\nAssessment: {status}; badge: {badge}; AI score: {overall_score}")
    return overall_score, badge
