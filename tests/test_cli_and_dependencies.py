import builtins
import json
from pathlib import Path
import subprocess
import sys

import pytest

from CurrentDocChecker import run_doc_quality_check
from DependencyChecker import inspect_dependencies
from FileFunctions import check_conda_file
from static_checks import compare_param_sets

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workflow(tmp_path):
    (tmp_path / 'main.nf').write_text('params.input = "data.csv"\n')
    (tmp_path / 'README.md').write_text('Run with --input.\n')
    (tmp_path / 'environment.yml').write_text('dependencies:\n  - python=3.12.11\n')
    return tmp_path


def cli(*args):
    return subprocess.run([sys.executable, '-B', '-m', 'CurrentDocChecker', *map(str, args)],
                          capture_output=True, text=True, timeout=20)


def test_static_cli_never_imports_ai(workflow, monkeypatch):
    real_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.startswith('langchain'):
            raise AssertionError('Static analysis imported an AI dependency')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    result = run_doc_quality_check(workflow, 'local', ['main.nf', 'README.md'], param_checking=True)
    assert result['overall_assessment']['status'] == 'PASS'
    assert result['overall_assessment']['score'] is None
    assert result['parameter_consistency']['status'] == 'PASS'


def test_cli_pass_and_reports(workflow, tmp_path):
    out = tmp_path / 'result.json'
    proc = cli(workflow, '--source-type', 'local', '--files', 'main.nf', 'README.md',
               '--usage_check', '--json-output', out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(out.read_text())['overall_assessment']['status'] == 'PASS'


def test_single_file_without_ai(workflow):
    out = workflow / 'single.json'
    proc = cli(workflow / 'README.md', '--source-type', 'local', '--json-output', out)
    assert proc.returncode == 1
    result = json.loads(out.read_text())
    assert result['files_checked'] == ['README.md']
    assert result['LLM-usage'] is False
    assert result['overall_assessment']['status'] == 'NOT_CHECKED'


def test_single_file_detects_workflow_language(tmp_path):
    source = tmp_path / 'Snakefile'
    source.write_text('x = config["sample"]')
    result = run_doc_quality_check(source, 'local')
    assert result['pipeline_type'] == 'snakemake'


def test_missing_selected_file_is_error(workflow):
    proc = cli(workflow, '--source-type', 'local', '--files', 'missing.nf', 'README.md')
    assert proc.returncode == 2
    assert 'Cannot read selected file' in proc.stdout


def test_output_write_failure_is_error(workflow):
    proc = cli(workflow, '--source-type', 'local', '--files', 'main.nf', 'README.md',
               '--json-output', workflow / 'absent' / 'result.json')
    assert proc.returncode == 2


def test_missing_dependency_evidence_is_incomplete(workflow):
    (workflow / 'environment.yml').unlink()
    result = run_doc_quality_check(workflow, 'local', ['main.nf', 'README.md'])
    assert not result['dependency_pinning']['all_pinned']
    assert result['overall_assessment']['status'] == 'NOT_CHECKED'


@pytest.mark.parametrize('dependency', ['python', 'python>=3.12', 'numpy=1.*', 'python~=3.12'])
def test_conda_ranges_are_not_exact_pins(tmp_path, dependency):
    source = tmp_path / 'environment.yml'
    source.write_text(f'dependencies:\n  - {dependency}\n')
    assert check_conda_file(source)


def test_nested_pip_pins(tmp_path):
    source = tmp_path / 'environment.yml'
    source.write_text('dependencies:\n  - python=3.12.11\n  - pip:\n    - numpy==2.2.0\n    - pandas>=2\n')
    assert check_conda_file(source) == ['pip: pandas>=2']
    result = inspect_dependencies(tmp_path, [], [source])
    assert result['status'] == 'FAIL'


def test_docker_scope_is_explicit(workflow):
    docker = workflow / 'Dockerfile'
    docker.write_text('FROM python:latest\n')
    result = inspect_dependencies(workflow, [docker], [workflow / 'environment.yml'])
    assert result['status'] == 'NOT_CHECKED'
    assert not result['all_pinned']
    assert 'Docker' in ' '.join(result['reasons'])


def test_empty_pip_block_is_not_evidence(tmp_path):
    source = tmp_path / 'environment.yml'
    source.write_text('dependencies:\n  - pip: []\n')
    assert inspect_dependencies(tmp_path, [], [source])['status'] == 'NOT_CHECKED'


def test_malformed_environment_is_error(workflow):
    (workflow / 'environment.yml').write_text('dependencies: [oops')
    proc = cli(workflow, '--source-type', 'local', '--files', 'main.nf', 'README.md')
    assert proc.returncode == 2


def test_no_doc_parameters_is_incomplete():
    assert compare_param_sets({'input'}, set(), set())['verdict'] == 'NOT_CHECKED'


def test_mismatch_exit(workflow):
    (workflow / 'README.md').write_text('Use --other.')
    proc = cli(workflow, '--source-type', 'local', '--files', 'main.nf', 'README.md', '--usage_check')
    assert proc.returncode == 1
    assert 'FAIL' in proc.stdout


def test_remote_cleanup_on_analysis_failure(workflow, monkeypatch):
    import CurrentDocChecker
    monkeypatch.setattr(CurrentDocChecker, 'gitgetter', lambda source: ([], [], str(workflow)))
    with pytest.raises(OSError):
        run_doc_quality_check('https://example.invalid/repo', files_to_check=['missing.nf'])
    assert not workflow.exists()


def test_unsupported_dependency_entry_is_error(workflow):
    (workflow / 'environment.yml').write_text('dependencies:\n  - unsupported: [something]\n')
    proc = cli(workflow, '--source-type', 'local', '--files', 'main.nf', 'README.md')
    assert proc.returncode == 2
    assert 'ERROR' in proc.stdout
