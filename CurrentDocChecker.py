import os
import getpass
import json
import argparse
import sys
import shutil
from pathlib import Path

from scoring import check_documentation_quality, extract_score_from_response, calculate_overall_score
from analysis import (get_file_type, _analyze_files, _print_comprehensive_report,
                      _check_dependencies, _check_param_consistency, _assign_badge)
from FileFunctions import gitgetter, load_files_from_config, find_files_robust


def _handle_single_file(source, json_output, add_to_report, output_file, json_output_file):
    """Handle single-file local mode. Returns report_lines list."""
    report_lines = []

    def _add(text):
        report_lines.append(text)
        add_to_report(text)

    _add(f"Checking single local file: {source}")
    try:
        with open(source, 'r', encoding='utf-8') as f:
            content = f.read()

        file_type = get_file_type(source)
        quality_report = check_documentation_quality(content, file_type)

        _add("\n=== DOCUMENTATION QUALITY REPORT ===")
        _add(quality_report)

        json_output["overall_assessment"]["score"] = extract_score_from_response(quality_report)
        json_output["overall_assessment"]["individual_scores"][source] = {
            "score": extract_score_from_response(quality_report),
            "type": file_type
        }

    except Exception as e:
        _add(f"Error reading file {source}: {e}")
        return report_lines

    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            _add(f"\n Report saved to: {output_file}")
        except Exception as e:
            _add(f"\n Error saving report to file: {e}")

    if json_output_file:
        try:
            with open(json_output_file, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=2, ensure_ascii=False)
            _add(f"\n JSON results saved to: {json_output_file}")
        except Exception as e:
            _add(f"\n Error saving JSON output to file: {e}")
 
    return report_lines


def run_doc_quality_check(source, source_type="github", files_to_check=None, output_file=None, json_output_file=None, param_checking=False, ai_usage=False, pipeline_type=None):
    """Main function to check documentation quality"""
    report_lines = []

    json_output = {
        "source": source,
        "source_type": source_type,
        "files_checked": files_to_check or [],
        "dependency_pinning": {
            "all_pinned": False,
            "unpinned_dependencies": []
        },
        "config_files": {
            "presence": False,
            "correctness_score": 0,
            "files_analyzed": []
        },
        "overall_assessment": {
            "score": 0,
            "medal": "No Badge",
            "individual_scores": {}
        },
        "parameter_consistency": {
            "checked": False,
            "results": ""
        },
        "analysis_timestamp": None, 
        "LLM-usage": ai_usage
    }

    def add_to_report(text):
        report_lines.append(text)
        print(text)

    add_to_report(f"Checking documentation quality for: {source}")

    from datetime import datetime
    json_output["analysis_timestamp"] = datetime.now().date().isoformat()

    if files_to_check is None:
        add_to_report("Error: files_to_check must be specified for custom mode")
        return report_lines

    repo_dir = None

    # --- Phase 1: Source-specific setup ---
    if source_type == "github":
        add_to_report("Downloading repository for analysis...")
        try:
            dockerfiles, conda_files, repo_dir = gitgetter(source)
            add_to_report(f"Repository downloaded to: {repo_dir}")
        except Exception as e:
            add_to_report(f"Error downloading repository: {e}")
            return report_lines

    elif source_type == "local":
        source_path = Path(source)
        if source_path.is_file():
            return _handle_single_file(source, json_output, add_to_report,
                                       output_file, json_output_file)
        elif source_path.is_dir():
            add_to_report(f"Checking local directory: {source}")
            repo_dir = source
            try:
                dockerfiles, conda_files = find_files_robust(repo_dir)
                add_to_report(f"Found {len(dockerfiles)} Dockerfiles and {len(conda_files)} conda files")
            except Exception as e:
                add_to_report(f"Warning: Could not scan for dependency files: {e}")
                dockerfiles, conda_files = [], []
        else:
            add_to_report(f"Error: {source} is neither a file nor a directory")
            return report_lines

    # --- Phase 2: Shared analysis pipeline ---
    all_reports = _analyze_files(repo_dir, files_to_check, pipeline_type, ai_usage, add_to_report)
    _print_comprehensive_report(all_reports, add_to_report)
    overall_score = calculate_overall_score(all_reports)

    overall_score += _check_dependencies(repo_dir, dockerfiles, conda_files, json_output, add_to_report)
    overall_score = min(overall_score, 10)

    overall_score += _check_param_consistency(repo_dir, files_to_check, param_checking,
                                              pipeline_type, json_output, add_to_report)
    overall_score = min(overall_score, 10)

    overall_score, badge = _assign_badge(overall_score, ai_usage, all_reports, json_output, add_to_report)

    # --- Phase 3: Cleanup (GitHub only) ---
    if source_type == "github" and repo_dir and os.path.exists(repo_dir):
        add_to_report(f"\nCleaning up downloaded repository: {repo_dir}")
        try:
            shutil.rmtree(repo_dir)
            add_to_report("Repository cleanup completed.")
        except Exception as e:
            add_to_report(f"Warning: Could not clean up repository: {e}")

    # Write report to file if output_file is specified
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            add_to_report(f"\n Report saved to: {output_file}")
        except Exception as e:
            add_to_report(f"\n Error saving report to file: {e}")

    # Write JSON output if json_output_file is specified
    if json_output_file:
        try:
            with open(json_output_file, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=2, ensure_ascii=False)
            add_to_report(f"\n JSON results saved to: {json_output_file}")
        except Exception as e:
            add_to_report(f"\n Error saving JSON output to file: {e}")

    return report_lines


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
        "--usage_check",
        action="store_true",
        help="Enable usage examples check (experimental)"
    )

    parser.add_argument(
        "--ai_analysis",
        action="store_true",
        help="Enable AI analysis (experimental)"
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
            return 1
    else:
        # No files specified - this is required for custom mode and local directory mode
        if args.source_type == "local":
            source_path = Path(args.source)
            if source_path.is_dir():
                print("Error: For local directory mode, you must specify files using either --files or --config")
                print("Use --help for usage examples")
                return 1
            # For local files, files_to_check can be None (single file mode)
        else:
            print("Error: For custom mode, you must specify files using either --files or --config")
            print("Use --help for usage examples")
            return 1

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

        report_lines = run_doc_quality_check(
            source=args.source,
            source_type=args.source_type,
            files_to_check=files_to_check,
            output_file=args.output,
            json_output_file=args.json_output,
            param_checking=args.usage_check,
            ai_usage=args.ai_analysis,
            pipeline_type=pipeline_type
        )

        print("\n✅ Documentation check completed successfully!")
        return 0

    except Exception as e:
        print(f"\n❌ Error during documentation check: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
