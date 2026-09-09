"""CLI for static and optional AI workflow documentation assessment."""
import argparse
import getpass
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from scoring import calculate_overall_score
from analysis import (_analyze_files, _print_comprehensive_report, _check_dependencies,
                      _check_param_consistency, _assign_badge)
from FileFunctions import gitgetter, load_files_from_config, find_files_robust


def run_doc_quality_check(source, source_type="github", files_to_check=None,
                          output_file=None, json_output_file=None,
                          param_checking=False, ai_usage=False, pipeline_type=None):
    """Assess selected files and return structured results; failures raise exceptions."""
    source = str(source)
    single_file = source_type == "local" and Path(source).is_file()
    if single_file:
        files_to_check = [Path(source).name]
    if not files_to_check:
        raise ValueError("Specify files using --files or --config for a repository/directory.")
    if source_type not in ("github", "local"):
        raise ValueError(f"Unsupported source type: {source_type}")
    from pipeline_analyzers import detect_pipeline_type
    pipeline_type = pipeline_type or detect_pipeline_type(files_to_check)
    result = {
        "source": source, "source_type": source_type,
        "files_checked": list(files_to_check), "pipeline_type": pipeline_type,
        "dependency_pinning": {"all_pinned": False, "status": "NOT_CHECKED",
                               "unpinned_dependencies": []},
        "config_files": {"presence": False, "correctness_score": None, "files_analyzed": []},
        "overall_assessment": {"score": None, "medal": "No Badge", "individual_scores": {}},
        "parameter_consistency": {"checked": False, "status": "NOT_CHECKED", "results": ""},
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(), "LLM-usage": ai_usage,
    }
    lines = []
    def add(text):
        lines.append(text)
        print(text)
    repo_dir = None
    try:
        if source_type == "github":
            dockerfiles, conda_files, repo_dir = gitgetter(source)
        else:
            repo_dir = str(Path(source).resolve().parent if single_file else Path(source).resolve())
            if not Path(repo_dir).is_dir():
                raise FileNotFoundError(f"Source directory does not exist: {source}")
            dockerfiles, conda_files = ([], []) if single_file else find_files_robust(repo_dir)
        add(f"Checking documentation quality for: {source}")
        reports = _analyze_files(repo_dir, files_to_check, pipeline_type, ai_usage, add)
        _print_comprehensive_report(reports, add)
        score = calculate_overall_score(reports) if ai_usage else 0.0
        score += _check_dependencies(repo_dir, dockerfiles, conda_files, result, add)
        score += _check_param_consistency(repo_dir, files_to_check, param_checking,
                                         pipeline_type, result, add)
        _assign_badge(max(0, min(score, 10)), ai_usage, reports, result, add)
    finally:
        if source_type == "github" and repo_dir:
            shutil.rmtree(repo_dir)
    if output_file:
        Path(output_file).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if json_output_file:
        Path(json_output_file).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Check documentation quality for GitHub repositories or local files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog= \
        """
        Examples:
        # Check with custom files via command line
        python CurrentDocChecker.py https://github.com/nf-core/rnaseq --files main.nf README.md docs/usage.md

        # Check with files from config file
        python CurrentDocChecker.py https://github.com/nf-core/rnaseq --config my_config.json

        # Check local file
        python CurrentDocChecker.py /path/to/main.nf --source-type local

        # Check local directory with specific files
        python CurrentDocChecker.py /path/to/project/ --source-type local --files main.nf README.md docs/usage.md

        # Check with custom output file
        python CurrentDocChecker.py https://github.com/nf-core/rnaseq --output report.txt --files main.nf README.md

        # Check with JSON output
        python CurrentDocChecker.py https://github.com/nf-core/rnaseq --json-output results.json --files main.nf README.md

        # Check with both text and JSON output
        python CurrentDocChecker.py https://github.com/nf-core/rnaseq --output report.txt --json-output results.json --files main.nf README.md
        """
    )

    parser.add_argument(
        "source",
        help="GitHub repository URL, local file path, or local directory path"
    )

    parser.add_argument(
        "--source-type",
        choices=["github", "local"],
        default="github",
        help="Type of source: 'github' for repository URL or 'local' for file/directory path (default: github)"
    )

    parser.add_argument(
        "--files",
        nargs="*",
        help="Custom list of files to check (space-separated)"
    )

    parser.add_argument(
        "--config",
        help="Path to configuration file for file selection"
    )

    parser.add_argument(
        "--output",
        help="Output file path for the report"
    )

    parser.add_argument(
        "--json-output",
        help="Output file path for JSON results"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--usage-check", "--usage_check", dest="usage_check",
        action="store_true",
        help="Check parameter consistency between selected code, configuration and documentation"
    )

    parser.add_argument(
        "--ai-analysis", "--ai_analysis", dest="ai_analysis",
        action="store_true",
        help="Enable optional Gemini analysis (requires the ai extra and GOOGLE_API_KEY)"
    )

    parser.add_argument(
        "--pipeline-type",
        choices=["nextflow", "snakemake", "cwl", "wdl"],
        default=None,
        help="Pipeline type (auto-detected from file extensions if not specified)"
    )

    return parser.parse_args()

def main():
    """Main function for command line interface"""
    args = parse_arguments()

    # Determine files to check
    files_to_check = None

    if args.files:
        # Use files from command line
        files_to_check = args.files
        print(f"Using custom files from command line: {files_to_check}")

    elif args.config:
        # Load files from config file
        files_to_check = load_files_from_config(args.config)
        if files_to_check:
            print(f"Using files from config file {args.config}: {files_to_check}")
        else:
            print(f"Could not load files from config file {args.config}")
            return 2
    else:
        # No files specified - this is required for custom mode and local directory mode
        if args.source_type == "local":
            source_path = Path(args.source)
            if source_path.is_dir():
                print("Error: For local directory mode, you must specify files using either --files or --config")
                print("Use --help for usage examples")
                return 2
            # For local files, files_to_check can be None (single file mode)
        else:
            print("Error: For custom mode, you must specify files using either --files or --config")
            print("Use --help for usage examples")
            return 2

    # Auto-detect pipeline type if not specified
    pipeline_type = args.pipeline_type
    if pipeline_type is None and files_to_check:
        from pipeline_analyzers import detect_pipeline_type
        pipeline_type = detect_pipeline_type(files_to_check)

    #Block out AI parts if check is not set to True

    if args.ai_analysis and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

    # Run the documentation check
    try:
        print(f"Starting documentation quality check for: {args.source}")
        print(f"Source type: {args.source_type}")
        print(f"Pipeline type: {pipeline_type}")
        if files_to_check:
            print(f"Files to check: {files_to_check}")

        result = run_doc_quality_check(
            source=args.source,
            source_type=args.source_type,
            files_to_check=files_to_check,
            output_file=args.output,
            json_output_file=args.json_output,
            param_checking=args.usage_check,
            ai_usage=args.ai_analysis,
            pipeline_type=pipeline_type
        )

        print(f"\nAssessment: {result['overall_assessment']['status']}")
        status = result["overall_assessment"]["status"]
        return 0 if status == "PASS" else 2 if status == "ERROR" else 1

    except Exception as e:
        print(f"\n❌ Error during documentation check: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
