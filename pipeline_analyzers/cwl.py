"""CWL (Common Workflow Language) pipeline analyzer."""

import re
from typing import Set

from .base import PipelineAnalyzer


class CwlAnalyzer(PipelineAnalyzer):

    name = "cwl"
    code_extensions = {'.cwl'}
    config_extensions = {'.yml', '.yaml'}

    BUILTINS = {
        'File', 'Directory', 'string', 'int', 'boolean', 'null',
        'float', 'double', 'long', 'Any',
    }

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith('.cwl')

    def get_file_role(self, file_path: str) -> str:
        lower = file_path.lower()
        if lower.endswith('.cwl'):
            return "code"
        return super().get_file_role(file_path)

    def extract_params_from_code(self, content: str) -> Set[str]:
        """Extract input names from CWL inputs: block."""
        params: Set[str] = set()
        try:
            import yaml
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'inputs' in data:
                inputs = data['inputs']
                if isinstance(inputs, dict):
                    params = set(inputs.keys())
                elif isinstance(inputs, list):
                    for item in inputs:
                        if isinstance(item, dict) and 'id' in item:
                            params.add(item['id'])
        except Exception:
            # Fallback regex: lines under inputs: that look like "  param_name:"
            in_inputs = False
            for line in content.split('\n'):
                if re.match(r'^inputs:', line):
                    in_inputs = True
                    continue
                if in_inputs and re.match(r'^[a-zA-Z]', line):
                    in_inputs = False
                if in_inputs:
                    m = re.match(r'^\s+(\w+):', line)
                    if m:
                        params.add(m.group(1))
        return params

    def extract_params_from_config(self, content: str) -> Set[str]:
        """CWL job input files are plain YAML with top-level keys."""
        params: Set[str] = set()
        try:
            import yaml
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                params = set(data.keys())
        except Exception:
            params.update(re.findall(r'^(\w+):', content, re.MULTILINE))
        return params

    def get_builtins(self) -> Set[str]:
        return self.BUILTINS
