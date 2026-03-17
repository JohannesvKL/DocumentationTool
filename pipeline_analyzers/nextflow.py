"""Nextflow pipeline analyzer — wraps existing static_checks.py logic."""

import re
from typing import Set

from .base import PipelineAnalyzer


class NextflowAnalyzer(PipelineAnalyzer):

    name = "nextflow"
    code_extensions = {'.nf'}
    config_extensions = {'.config'}

    BUILTINS = {
        'help', 'version', 'resume', 'profile', 'name', 'with_report',
        'with_trace', 'with_timeline', 'with_dag', 'work_dir', 'launchDir',
        'projectDir', 'baseDir', 'outdir', 'publish_dir_mode', 'enable_conda',
        'singularity_pull_docker_container', 'max_memory', 'max_cpus', 'max_time',
        'validationShowHiddenParams', 'validationFailUnrecognisedParams',
        'validationLenientMode', 'monochrome_logs', 'show_hidden_params',
        'schema_ignore_params', 'validate_params',
    }

    def can_handle(self, file_path: str) -> bool:
        lower = file_path.lower()
        return (lower.endswith('.nf') or lower.endswith('.config')
                or 'nextflow' in lower)

    def get_file_role(self, file_path: str) -> str:
        lower = file_path.lower()
        if lower.endswith('.nf'):
            return "code"
        if lower.endswith('.config') or 'config' in lower:
            return "config"
        if lower.endswith('.md') or 'readme' in lower:
            return "doc"
        return "generic"

    def extract_params_from_code(self, content: str) -> Set[str]:
        return set(re.findall(r'params\.(\w+)', content))

    def extract_params_from_config(self, content: str) -> Set[str]:
        params: Set[str] = set()
        params.update(re.findall(r'params\.(\w+)\s*=', content))
        for block in re.findall(r'params\s*\{([^}]+)\}', content, re.DOTALL):
            params.update(re.findall(r'^\s*(\w+)\s*=', block, re.MULTILINE))
        return params

    def get_builtins(self) -> Set[str]:
        return self.BUILTINS
