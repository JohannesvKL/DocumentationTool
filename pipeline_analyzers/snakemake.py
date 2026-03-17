"""Snakemake pipeline analyzer."""

import os
import re
from typing import Set

from .base import PipelineAnalyzer


class SnakemakeAnalyzer(PipelineAnalyzer):

    name = "snakemake"
    code_extensions = {'.smk'}          # plus filename-based Snakefile detection
    config_extensions = {'.yaml', '.yml', '.json'}

    BUILTINS = {
        'input', 'output', 'params', 'log', 'threads', 'resources',
        'benchmark', 'shell', 'run', 'script', 'wrapper', 'conda',
        'singularity', 'container', 'envmodules', 'wildcard_constraints',
    }

    def can_handle(self, file_path: str) -> bool:
        lower = file_path.lower()
        basename = os.path.basename(lower)
        return (lower.endswith('.smk')
                or basename == 'snakefile'
                or basename.startswith('snakefile.'))

    def get_file_role(self, file_path: str) -> str:
        lower = file_path.lower()
        basename = os.path.basename(lower)
        if lower.endswith('.smk') or basename == 'snakefile' or basename.startswith('snakefile.'):
            return "code"
        if basename.startswith('config') and any(
            lower.endswith(ext) for ext in self.config_extensions
        ):
            return "config"
        return super().get_file_role(file_path)

    def extract_params_from_code(self, content: str) -> Set[str]:
        params: Set[str] = set()
        # config["key"] and config['key']
        params.update(re.findall(r'config\[["\'](\w+)["\']\]', content))
        # config.get("key", ...) and config.get('key', ...)
        params.update(re.findall(r'config\.get\(["\'](\w+)["\']', content))
        return params

    def extract_params_from_config(self, content: str) -> Set[str]:
        """Extract top-level keys from YAML or JSON config."""
        params: Set[str] = set()
        try:
            import yaml
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                params = set(data.keys())
        except Exception:
            # Fallback: regex for top-level YAML keys
            params.update(re.findall(r'^(\w+):', content, re.MULTILINE))
        return params

    def get_builtins(self) -> Set[str]:
        return self.BUILTINS
