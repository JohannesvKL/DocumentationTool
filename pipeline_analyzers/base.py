"""Abstract base class for pipeline-type-specific static analysis."""

from abc import ABC, abstractmethod
from typing import Dict, Set, Any


class PipelineAnalyzer(ABC):
    """Base class for pipeline analyzers.

    Each subclass handles a specific workflow language (Nextflow, Snakemake,
    CWL, WDL).  Follows the same Strategy pattern as
    ``comparators.base.FileComparator``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Pipeline type identifier, e.g. 'nextflow', 'snakemake'."""
        ...

    @property
    @abstractmethod
    def code_extensions(self) -> Set[str]:
        """File extensions for pipeline code files, e.g. {'.nf'}."""
        ...

    @property
    @abstractmethod
    def config_extensions(self) -> Set[str]:
        """File extensions for config files, e.g. {'.config'}."""
        ...

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Return True if this analyzer recognizes the file."""
        ...

    def get_file_role(self, file_path: str) -> str:
        """Classify a file as 'code', 'config', 'doc', or 'generic'.

        Default implementation uses extensions.  Subclasses may override for
        filename-based detection (e.g. ``Snakefile``).
        """
        lower = file_path.lower()
        if any(lower.endswith(ext) for ext in self.code_extensions):
            return "code"
        if any(lower.endswith(ext) for ext in self.config_extensions):
            return "config"
        if lower.endswith('.md') or 'readme' in lower:
            return "doc"
        return "generic"

    @abstractmethod
    def extract_params_from_code(self, content: str) -> Set[str]:
        """Extract parameter names from pipeline code file content."""
        ...

    @abstractmethod
    def extract_params_from_config(self, content: str) -> Set[str]:
        """Extract parameter names from config file content."""
        ...

    @abstractmethod
    def get_builtins(self) -> Set[str]:
        """Return set of built-in / reserved names to filter."""
        ...

    def get_tool_metadata(self) -> Dict[str, Any]:
        """Return metadata dict for result dicts / RO-Crate."""
        return {"tool": f"static_checks_{self.name}", "version": "1.0"}
