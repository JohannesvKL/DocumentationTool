"""Tests for the static_checks module."""

import os
import tempfile
import pytest

# Ensure Code/ is on the path so static_checks can be imported
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fixtures'))

from static_checks import (
    extract_params_from_nextflow,
    extract_params_from_config,
    extract_params_from_markdown,
    compare_param_sets,
    run_static_param_check,
    NEXTFLOW_BUILTINS,
)

# ---------------------------------------------------------------------------
# Fixtures — paths to test data shipped with the repo
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
MIN_TEST_NF = os.path.join(FIXTURES_DIR, 'Min_Test.nf')
README_TEST_MD = os.path.join(FIXTURES_DIR, 'ReadMe_Test.md')


# ---------------------------------------------------------------------------
# extract_params_from_nextflow
# ---------------------------------------------------------------------------

class TestExtractParamsFromNextflow:
    def test_basic_params(self):
        content = "params.input = 'data'\nparams.output = 'results'"
        result = extract_params_from_nextflow(content)
        assert result == {'input', 'output'}

    def test_references_without_assignment(self):
        content = "Channel.fromPath(params.input)\nprintln(params.verbose)"
        result = extract_params_from_nextflow(content)
        assert 'input' in result
        assert 'verbose' in result

    def test_min_test_fixture(self):
        if not os.path.exists(MIN_TEST_NF):
            pytest.skip("Min_Test.nf fixture not found")
        with open(MIN_TEST_NF) as f:
            content = f.read()
        result = extract_params_from_nextflow(content)
        assert 'message' in result
        assert 'count' in result

    def test_empty_content(self):
        assert extract_params_from_nextflow('') == set()


# ---------------------------------------------------------------------------
# extract_params_from_config
# ---------------------------------------------------------------------------

class TestExtractParamsFromConfig:
    def test_flat_style(self):
        content = "params.input = 'data'\nparams.threads = 4"
        result = extract_params_from_config(content)
        assert result == {'input', 'threads'}

    def test_block_style(self):
        content = """
params {
    input  = 'data'
    output = 'results'
    threads = 4
}
"""
        result = extract_params_from_config(content)
        assert result == {'input', 'output', 'threads'}

    def test_mixed_style(self):
        content = """
params.global_opt = true
params {
    input = 'data'
}
"""
        result = extract_params_from_config(content)
        assert 'global_opt' in result
        assert 'input' in result

    def test_empty_content(self):
        assert extract_params_from_config('') == set()


# ---------------------------------------------------------------------------
# extract_params_from_markdown
# ---------------------------------------------------------------------------

class TestExtractParamsFromMarkdown:
    def test_double_dash_flags(self):
        content = "Run with `--input` and `--output` flags."
        result = extract_params_from_markdown(content)
        assert 'input' in result
        assert 'output' in result

    def test_params_dot_references(self):
        content = "Set `params.threads` to control parallelism."
        result = extract_params_from_markdown(content)
        assert 'threads' in result

    def test_filters_builtins(self):
        content = "Use --help, --version, --resume, --input"
        result = extract_params_from_markdown(content)
        assert 'input' in result
        assert 'help' not in result
        assert 'version' not in result
        assert 'resume' not in result

    def test_readme_fixture(self):
        if not os.path.exists(README_TEST_MD):
            pytest.skip("ReadMe_Test.md fixture not found")
        with open(README_TEST_MD) as f:
            content = f.read()
        result = extract_params_from_markdown(content)
        assert 'message' in result
        assert 'count' in result

    def test_empty_content(self):
        assert extract_params_from_markdown('') == set()


# ---------------------------------------------------------------------------
# compare_param_sets
# ---------------------------------------------------------------------------

class TestCompareParamSets:
    def test_consistent_sets(self):
        s = {'input', 'output'}
        result = compare_param_sets(s, s, s)
        assert result['match'] is True
        assert result['verdict'] == 'PASS'
        assert 'MISMATCH' not in result['report']

    def test_mismatched_sets(self):
        code = {'input', 'output', 'threads'}
        doc = {'input', 'output'}
        config = {'input', 'output'}
        result = compare_param_sets(code, config, doc)
        assert result['match'] is False
        assert result['verdict'] == 'FAIL'
        assert 'MISMATCH' in result['report']
        assert 'threads' in result['report']

    def test_empty_sets(self):
        result = compare_param_sets(set(), set(), set())
        assert result['match'] is False
        assert result['verdict'] == 'NOT_CHECKED'

    def test_result_dict_format(self):
        result = compare_param_sets({'a'}, {'a'}, {'a'})
        required_keys = {'match', 'method', 'verdict', 'reason', 'tool_metadata', 'configuration', 'summary', 'report'}
        assert required_keys.issubset(result.keys())

    def test_partial_sets(self):
        """When only code and doc sets are provided (config empty)."""
        code = {'input', 'output'}
        doc = {'input'}
        result = compare_param_sets(code, set(), doc)
        assert result['match'] is False
        assert 'output' in result['report']


# ---------------------------------------------------------------------------
# Integration: run_static_param_check
# ---------------------------------------------------------------------------

class TestRunStaticParamCheck:
    def test_with_temp_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a small .nf file
            nf_content = "params.input = 'data'\nparams.output = 'results'"
            with open(os.path.join(tmpdir, 'main.nf'), 'w') as f:
                f.write(nf_content)

            # Write a config
            cfg_content = "params {\n    input = 'data'\n    output = 'results'\n}"
            with open(os.path.join(tmpdir, 'nextflow.config'), 'w') as f:
                f.write(cfg_content)

            # Write a readme
            md_content = "# Pipeline\n## Usage\nRun with `--input` and `--output`."
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write(md_content)

            result = run_static_param_check(tmpdir, ['main.nf', 'nextflow.config', 'README.md'])
            assert result['verdict'] in ('PASS', 'FAIL')
            assert 'match' in result
            assert 'report' in result

    def test_consistent_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'main.nf'), 'w') as f:
                f.write("params.input = 'x'\nparams.output = 'y'")
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write("Use `--input` and `--output`.")

            result = run_static_param_check(tmpdir, ['main.nf', 'README.md'])
            assert result['match'] is True
            assert result['verdict'] == 'PASS'

    def test_inconsistent_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'main.nf'), 'w') as f:
                f.write("params.input = 'x'\nparams.threads = 4")
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write("Use `--input` flag.")

            result = run_static_param_check(tmpdir, ['main.nf', 'README.md'])
            assert result['match'] is False
            assert 'MISMATCH' in result['report']

    def test_missing_files_handled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_static_param_check(tmpdir, ['nonexistent.nf'])
            # Missing evidence is an execution error, never a passing assessment.
            assert result['verdict'] == 'ERROR'

    def test_with_fixture_files(self):
        """Integration test using the actual Min_Test.nf and ReadMe_Test.md fixtures."""
        if not os.path.exists(MIN_TEST_NF) or not os.path.exists(README_TEST_MD):
            pytest.skip("Fixture files not found")
        result = run_static_param_check(FIXTURES_DIR, ['Min_Test.nf', 'ReadMe_Test.md'])
        assert 'match' in result
        assert 'report' in result
        # Both files mention 'message' and 'count'
        assert result['verdict'] in ('PASS', 'FAIL')
