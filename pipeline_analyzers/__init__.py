"""Pipeline analyzer registry and auto-detection."""

from .base import PipelineAnalyzer
from .nextflow import NextflowAnalyzer
from .snakemake import SnakemakeAnalyzer
from .cwl import CwlAnalyzer
from .wdl import WdlAnalyzer

# Ordered registry — checked in order for auto-detection
_ANALYZERS = [
    NextflowAnalyzer(),
    SnakemakeAnalyzer(),
    CwlAnalyzer(),
    WdlAnalyzer(),
]

_ANALYZER_MAP = {a.name: a for a in _ANALYZERS}


def get_analyzer(pipeline_type: str) -> PipelineAnalyzer:
    """Get analyzer by explicit name.  Raises KeyError if unknown."""
    return _ANALYZER_MAP[pipeline_type]


def detect_pipeline_type(file_paths: list) -> str:
    """Auto-detect pipeline type from a list of file paths.

    Returns the name of the first analyzer that can handle any file.
    Falls back to ``'nextflow'`` for backward compatibility.
    """
    for analyzer in _ANALYZERS:
        for fp in file_paths:
            if analyzer.can_handle(fp):
                return analyzer.name
    return "nextflow"


def get_analyzer_for_files(file_paths: list,
                           pipeline_type: str = None) -> PipelineAnalyzer:
    """Get the right analyzer: explicit type wins, else auto-detect."""
    if pipeline_type:
        return get_analyzer(pipeline_type)
    detected = detect_pipeline_type(file_paths)
    return get_analyzer(detected)
