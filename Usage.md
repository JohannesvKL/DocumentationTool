# CurrentDocChecker — Usage

Python script with an optional LLM-backend for checking documentation quality for GitHub repositories or local files.

```
python CurrentDocChecker.py <source> [options]
```

## Arguments

| Argument | Description |
|---|---|
| `source` | GitHub repository URL, local file path, or local directory path |

## Options

| Flag | Values | Default | Description |
|---|---|---|---|
| `--source-type` | `github`, `local` | `github` | Source type: GitHub URL or local path |
| `--files` | `file1 file2 ...` | — | Files to check (space-separated) |
| `--config` | `<path>` | — | Config file for file selection |
| `--output` | `<path>` | — | Output file path for the text report |
| `--json-output` | `<path>` | — | Output file path for JSON results |
| `--pipeline-type` | `nextflow`, `snakemake`, `cwl`, `wdl` | auto-detected | Pipeline type |
| `--verbose` | — | — | Enable verbose output |
| `--usage_check` | — | — | *(Experimental)* Check usage examples |
| `--ai_analysis` | — | — | *(Experimental)* Enable AI analysis |

## Examples

**Check specific files in a GitHub repo**
```bash
python CurrentDocChecker.py https://github.com/nf-core/rnaseq \
  --files main.nf README.md docs/usage.md
```

**Use a config file for file selection**
```bash
python CurrentDocChecker.py https://github.com/nf-core/rnaseq \
  --config my_config.json
```

**Check a local file**
```bash
python CurrentDocChecker.py /path/to/main.nf --source-type local
```

**Check a local directory with specific files**
```bash
python CurrentDocChecker.py /path/to/project/ \
  --source-type local --files main.nf README.md docs/usage.md
```

**Write a text report**
```bash
python CurrentDocChecker.py https://github.com/nf-core/rnaseq \
  --output report.txt --files main.nf README.md
```

**Write a JSON report**
```bash
python CurrentDocChecker.py https://github.com/nf-core/rnaseq \
  --json-output results.json --files main.nf README.md
```

**Write both text and JSON output**
```bash
python CurrentDocChecker.py https://github.com/nf-core/rnaseq \
  --output report.txt --json-output results.json --files main.nf README.md
```
