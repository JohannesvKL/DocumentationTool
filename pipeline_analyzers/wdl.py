"""WDL (Workflow Description Language) pipeline analyzer."""

import re
import json as json_mod
from typing import Set

from .base import PipelineAnalyzer


class WdlAnalyzer(PipelineAnalyzer):

    name = "wdl"
    code_extensions = {'.wdl'}
    config_extensions = {'.json'}

    BUILTINS = {
        'String', 'Int', 'Float', 'Boolean', 'File',
        'Array', 'Map', 'Pair', 'Object',
    }

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith('.wdl')

    def extract_params_from_code(self, content: str) -> Set[str]:
        """Extract input variable names from WDL ``input { ... }`` blocks."""
        params: Set[str] = set()
        for block in re.finditer(r'input\s*\{([^}]+)\}', content, re.DOTALL):
            block_text = block.group(1)
            for line in block_text.split('\n'):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                # Type Name  or  Type Name = default
                # Handle Array[Type], Map[K,V], etc.
                m = re.match(
                    r'(?:Array|Map|Pair)?\[?[\w?.]+\]?\s+(\w+)',
                    line,
                )
                if m:
                    name = m.group(1)
                    if name not in self.BUILTINS:
                        params.add(name)
        return params

    def extract_params_from_config(self, content: str) -> Set[str]:
        """WDL input JSON files: extract leaf variable names from dotted keys."""
        params: Set[str] = set()
        try:
            data = json_mod.loads(content)
            if isinstance(data, dict):
                for key in data.keys():
                    # Keys like "workflow.task.varname" → use leaf
                    parts = key.split('.')
                    params.add(parts[-1])
        except Exception:
            # Fallback: extract quoted keys
            params.update(re.findall(r'"[\w.]*\.(\w+)"', content))
        return params

    def get_builtins(self) -> Set[str]:
        return self.BUILTINS
