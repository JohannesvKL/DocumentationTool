"""
Static (AI-free) analysis for Nextflow pipeline documentation.

Provides parameter extraction from .nf, .config, and markdown files,
and cross-file parameter consistency comparison.
All results use the comparator result dict format (match, verdict, summary, etc.).
"""

import re
import os
from typing import Dict, Set, Optional


# Built-in Nextflow params that should be excluded from consistency checks
NEXTFLOW_BUILTINS = {
    'help', 'version', 'resume', 'profile', 'name', 'with_report',
    'with_trace', 'with_timeline', 'with_dag', 'work_dir', 'launchDir',
    'projectDir', 'baseDir', 'outdir', 'publish_dir_mode', 'enable_conda',
    'singularity_pull_docker_container', 'max_memory', 'max_cpus', 'max_time',
    'validationShowHiddenParams', 'validationFailUnrecognisedParams',
    'validationLenientMode', 'monochrome_logs', 'show_hidden_params',
    'schema_ignore_params', 'validate_params',
}


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

def extract_params_from_nextflow(content: str) -> Set[str]:
    """Extract parameter names from Nextflow (.nf) file content.

    Catches both ``params.X = val`` definitions and ``params.X`` references.
    """
    params = set(re.findall(r'params\.(\w+)', content))
    return params


def extract_params_from_config(content: str) -> Set[str]:
    """Extract parameter names from Nextflow config file content.

    Handles:
    - ``params { name = val }`` block style
    - ``params.name = val`` flat style
    """
    params: Set[str] = set()

    # Flat style: params.name = ...
    params.update(re.findall(r'params\.(\w+)\s*=', content))

    # Block style: params { ... }
    block_match = re.findall(r'params\s*\{([^}]+)\}', content, re.DOTALL)
    for block in block_match:
        # Inside the block, lines like "  name = value"
        params.update(re.findall(r'^\s*(\w+)\s*=', block, re.MULTILINE))

    return params


def extract_params_from_markdown(content: str, builtins: Optional[Set[str]] = None) -> Set[str]:
    """Extract parameter names from markdown documentation.

    Multi-pattern approach:
    - ``--param`` flags (with or without backticks)
    - ``params.X`` references
    - Markdown table rows with param-like entries

    *builtins* defaults to ``NEXTFLOW_BUILTINS`` for backward compatibility.
    """
    if builtins is None:
        builtins = NEXTFLOW_BUILTINS

    params: Set[str] = set()

    # --param style (with optional backtick wrapping)
    params.update(re.findall(r'`?--(\w+)`?', content))

    # params.X references
    params.update(re.findall(r'params\.(\w+)', content))

    # Markdown table rows: | `--param` | ... |  or | param | ... |
    for row in re.findall(r'^\|[^|]*\|', content, re.MULTILINE):
        table_params = re.findall(r'`?--(\w+)`?', row)
        params.update(table_params)

    # Filter built-ins
    params -= builtins

    return params


# ---------------------------------------------------------------------------
# Cross-file comparison
# ---------------------------------------------------------------------------

def compare_param_sets(
    code_params: Set[str],
    config_params: Set[str],
    doc_params: Set[str],
) -> Dict:
    """Compare parameter sets across code, config, and documentation files.

    Returns a comparator-format result dict with keys:
    match, verdict, summary, report, tool_metadata, method, configuration.
    """
    all_params = code_params | config_params | doc_params
    if not all_params:
        return _make_result(
            match=False,
            verdict="NOT_CHECKED",
            summary="No parameters found in any file.",
            report="No parameters detected across code, config, or documentation files.",
        )

    if not code_params or not doc_params:
        return _make_result(False, "NOT_CHECKED", "Insufficient parameter evidence.",
                            "Parameter consistency not checked: need parameters extracted from both code and documentation.")

    # Compute mismatches per direction
    in_code_not_doc = code_params - doc_params if doc_params else set()
    in_doc_not_code = doc_params - code_params if code_params else set()
    in_code_not_config = code_params - config_params if config_params else set()
    in_config_not_code = config_params - code_params if code_params else set()

    has_mismatches = bool(in_code_not_doc or in_doc_not_code or in_code_not_config or in_config_not_code)

    # Consistency ratio: intersection / union
    sets_present = [s for s in (code_params, config_params, doc_params) if s]
    if len(sets_present) >= 2:
        intersection = set.intersection(*sets_present)
        union = set.union(*sets_present)
        consistency_ratio = len(intersection) / len(union) if union else 1.0
    else:
        consistency_ratio = 1.0

    # Build report lines
    report_lines = []
    report_lines.append(f"Parameter consistency ratio: {consistency_ratio:.0%}")
    report_lines.append(f"Total unique parameters found: {len(all_params)}")
    report_lines.append(f"  Code params: {len(code_params)}")
    report_lines.append(f"  Config params: {len(config_params)}")
    report_lines.append(f"  Doc params: {len(doc_params)}")
    report_lines.append("")

    if in_code_not_doc:
        report_lines.append(f"MISMATCH: Parameters in code but missing from docs: {', '.join(sorted(in_code_not_doc))}")
    if in_doc_not_code:
        report_lines.append(f"MISMATCH: Parameters in docs but not in code: {', '.join(sorted(in_doc_not_code))}")
    if in_code_not_config:
        report_lines.append(f"MISMATCH: Parameters in code but missing from config: {', '.join(sorted(in_code_not_config))}")
    if in_config_not_code:
        report_lines.append(f"MISMATCH: Parameters in config but not in code: {', '.join(sorted(in_config_not_code))}")

    if not has_mismatches:
        report_lines.append("All parameter sets are consistent.")

    verdict = "FAIL" if has_mismatches else "PASS"
    summary = (
        f"Parameter consistency: {consistency_ratio:.0%} "
        f"({len(all_params)} unique params). "
        + (f"{sum(bool(s) for s in [in_code_not_doc, in_doc_not_code, in_code_not_config, in_config_not_code])} mismatch direction(s) found."
           if has_mismatches else "All sets consistent.")
    )
    report = "\n".join(report_lines)

    return _make_result(
        match=not has_mismatches,
        verdict=verdict,
        summary=summary,
        report=report,
    )


def _make_result(match: bool, verdict: str, summary: str, report: str) -> Dict:
    """Build a standardized comparator result dict."""
    return {
        "match": match,
        "method": "static_param_analysis",
        "verdict": verdict,
        "reason": summary,
        "tool_metadata": {
            "tool": "static_checks",
            "version": "1.0",
        },
        "configuration": {},
        "summary": summary,
        "report": report,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_static_param_check(repo_dir: str, files_to_check: list,
                           pipeline_type: Optional[str] = None) -> Dict:
    """Read all specified files, extract params per type, and compare.

    Uses the ``PipelineAnalyzer`` for *pipeline_type* (defaults to
    ``"nextflow"``) to classify files and extract parameters.

    Returns a comparator-format result dict from ``compare_param_sets``.
    """
    from pipeline_analyzers import get_analyzer
    analyzer = get_analyzer(pipeline_type or "nextflow")
    builtins = analyzer.get_builtins()

    code_params: Set[str] = set()
    config_params: Set[str] = set()
    doc_params: Set[str] = set()

    for file_path in files_to_check:
        full_path = os.path.join(repo_dir, file_path)
        if not os.path.isfile(full_path):
            return _make_result(False, "ERROR", "Selected file missing.", f"Cannot read {file_path}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError as e:
            return _make_result(False, "ERROR", "Selected file unreadable.", str(e))

        role = analyzer.get_file_role(file_path)
        if role == "code":
            code_params |= analyzer.extract_params_from_code(content)
        elif role == "config":
            config_params |= analyzer.extract_params_from_config(content)
        elif role == "doc":
            doc_params |= extract_params_from_markdown(content, builtins=builtins)

    code_params -= builtins
    config_params -= builtins

    return compare_param_sets(code_params, config_params, doc_params)
