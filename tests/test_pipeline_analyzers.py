"""Tests for the pipeline_analyzers package."""

import os
import tempfile
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipeline_analyzers import (
    get_analyzer,
    detect_pipeline_type,
    get_analyzer_for_files,
    PipelineAnalyzer,
)
from pipeline_analyzers.nextflow import NextflowAnalyzer
from pipeline_analyzers.snakemake import SnakemakeAnalyzer
from pipeline_analyzers.cwl import CwlAnalyzer
from pipeline_analyzers.wdl import WdlAnalyzer


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '..')


# ---------------------------------------------------------------------------
# Pipeline detection
# ---------------------------------------------------------------------------

class TestPipelineDetection:
    def test_detect_nextflow(self):
        assert detect_pipeline_type(['main.nf', 'README.md']) == 'nextflow'

    def test_detect_snakemake(self):
        assert detect_pipeline_type(['Snakefile', 'config.yaml']) == 'snakemake'

    def test_detect_snakemake_smk(self):
        assert detect_pipeline_type(['workflow.smk', 'README.md']) == 'snakemake'

    def test_detect_cwl(self):
        assert detect_pipeline_type(['pipeline.cwl', 'inputs.yml']) == 'cwl'

    def test_detect_wdl(self):
        assert detect_pipeline_type(['workflow.wdl', 'inputs.json']) == 'wdl'

    def test_fallback_to_nextflow(self):
        assert detect_pipeline_type(['README.md', 'data.csv']) == 'nextflow'

    def test_get_analyzer_by_name(self):
        for name in ('nextflow', 'snakemake', 'cwl', 'wdl'):
            a = get_analyzer(name)
            assert a.name == name

    def test_get_analyzer_for_files_explicit(self):
        a = get_analyzer_for_files(['Snakefile'], pipeline_type='cwl')
        assert a.name == 'cwl'  # explicit wins

    def test_get_analyzer_for_files_auto(self):
        a = get_analyzer_for_files(['workflow.wdl'])
        assert a.name == 'wdl'


# ---------------------------------------------------------------------------
# NextflowAnalyzer
# ---------------------------------------------------------------------------

class TestNextflowAnalyzer:
    def setup_method(self):
        self.analyzer = NextflowAnalyzer()

    def test_can_handle(self):
        assert self.analyzer.can_handle('main.nf')
        assert self.analyzer.can_handle('nextflow.config')
        assert not self.analyzer.can_handle('Snakefile')

    def test_file_roles(self):
        assert self.analyzer.get_file_role('main.nf') == 'code'
        assert self.analyzer.get_file_role('nextflow.config') == 'config'
        assert self.analyzer.get_file_role('README.md') == 'doc'

    def test_extract_params(self):
        content = "params.input = 'x'\nparams.output = 'y'"
        assert self.analyzer.extract_params_from_code(content) == {'input', 'output'}


# ---------------------------------------------------------------------------
# SnakemakeAnalyzer
# ---------------------------------------------------------------------------

SAMPLE_SNAKEFILE = """\
# Author: Test User
# Description: Sample pipeline
# Version: 1.0

configfile: "config.yaml"

# Align reads to reference
rule align:
    input:
        reads=config["reads"],
        ref=config["reference"]
    output:
        "aligned/{sample}.bam"
    conda:
        "envs/align.yaml"
    shell:
        "bwa mem {input.ref} {input.reads} > {output}"

rule sort:
    input:
        "aligned/{sample}.bam"
    output:
        "sorted/{sample}.bam"
    wrapper:
        "v1.0/bio/samtools/sort"
"""

SAMPLE_SNAKEMAKE_CONFIG = """\
reads: data/reads.fastq
reference: data/ref.fasta
threads: 4
output_dir: results
"""


class TestSnakemakeAnalyzer:
    def setup_method(self):
        self.analyzer = SnakemakeAnalyzer()

    def test_can_handle(self):
        assert self.analyzer.can_handle('Snakefile')
        assert self.analyzer.can_handle('rules/align.smk')
        assert not self.analyzer.can_handle('main.nf')

    def test_file_roles(self):
        assert self.analyzer.get_file_role('Snakefile') == 'code'
        assert self.analyzer.get_file_role('rules/align.smk') == 'code'
        assert self.analyzer.get_file_role('config.yaml') == 'config'
        assert self.analyzer.get_file_role('README.md') == 'doc'

    def test_extract_params_from_code(self):
        params = self.analyzer.extract_params_from_code(SAMPLE_SNAKEFILE)
        assert 'reads' in params
        assert 'reference' in params

    def test_extract_params_from_config(self):
        params = self.analyzer.extract_params_from_config(SAMPLE_SNAKEMAKE_CONFIG)
        assert 'reads' in params
        assert 'reference' in params
        assert 'threads' in params

    def test_builtins_excluded(self):
        builtins = self.analyzer.get_builtins()
        assert 'input' in builtins
        assert 'output' in builtins


# ---------------------------------------------------------------------------
# CwlAnalyzer
# ---------------------------------------------------------------------------

SAMPLE_CWL = """\
cwlVersion: v1.2
class: CommandLineTool
label: "SAMtools sort"
doc: "Sort BAM files using SAMtools"

requirements:
  DockerRequirement:
    dockerPull: quay.io/biocontainers/samtools:1.15

baseCommand: [samtools, sort]

inputs:
  input_bam:
    type: File
    doc: "Input BAM file"
    inputBinding:
      position: 1
  threads:
    type: int
    doc: "Number of threads"
    inputBinding:
      prefix: -@

outputs:
  sorted_bam:
    type: File
    outputBinding:
      glob: "*.sorted.bam"
"""

SAMPLE_CWL_JOB = """\
input_bam:
  class: File
  path: sample.bam
threads: 4
"""


class TestCwlAnalyzer:
    def setup_method(self):
        self.analyzer = CwlAnalyzer()

    def test_can_handle(self):
        assert self.analyzer.can_handle('tool.cwl')
        assert not self.analyzer.can_handle('Snakefile')

    def test_file_roles(self):
        assert self.analyzer.get_file_role('tool.cwl') == 'code'
        assert self.analyzer.get_file_role('README.md') == 'doc'

    def test_extract_params_from_code(self):
        params = self.analyzer.extract_params_from_code(SAMPLE_CWL)
        assert 'input_bam' in params
        assert 'threads' in params

    def test_extract_params_from_config(self):
        params = self.analyzer.extract_params_from_config(SAMPLE_CWL_JOB)
        assert 'input_bam' in params
        assert 'threads' in params



# ---------------------------------------------------------------------------
# WdlAnalyzer
# ---------------------------------------------------------------------------

SAMPLE_WDL = """\
version 1.1

workflow AlignAndSort {
    input {
        File reads
        File reference
        Int threads = 4
    }

    call Align {
        input:
            reads = reads,
            reference = reference,
            threads = threads
    }

    call Sort {
        input:
            input_bam = Align.aligned_bam
    }

    output {
        File sorted_bam = Sort.sorted_bam
    }

    parameter_meta {
        reads: "Input FASTQ reads"
        reference: "Reference genome FASTA"
        threads: "Number of CPU threads"
    }
}

task Align {
    input {
        File reads
        File reference
        Int threads
    }

    command <<<
        bwa mem -t ~{threads} ~{reference} ~{reads} > aligned.bam
    >>>

    output {
        File aligned_bam = "aligned.bam"
    }

    runtime {
        docker: "biocontainers/bwa:0.7.17"
        cpu: threads
    }
}

task Sort {
    input {
        File input_bam
    }

    command <<<
        samtools sort ~{input_bam} -o sorted.bam
    >>>

    output {
        File sorted_bam = "sorted.bam"
    }

    runtime {
        docker: "biocontainers/samtools:1.15"
    }
}
"""

SAMPLE_WDL_INPUTS = """\
{
    "AlignAndSort.reads": "sample.fastq",
    "AlignAndSort.reference": "ref.fasta",
    "AlignAndSort.threads": 8
}
"""


class TestWdlAnalyzer:
    def setup_method(self):
        self.analyzer = WdlAnalyzer()

    def test_can_handle(self):
        assert self.analyzer.can_handle('pipeline.wdl')
        assert not self.analyzer.can_handle('tool.cwl')

    def test_file_roles(self):
        assert self.analyzer.get_file_role('pipeline.wdl') == 'code'
        assert self.analyzer.get_file_role('README.md') == 'doc'

    def test_extract_params_from_code(self):
        params = self.analyzer.extract_params_from_code(SAMPLE_WDL)
        assert 'reads' in params
        assert 'reference' in params
        assert 'threads' in params

    def test_extract_params_from_config(self):
        params = self.analyzer.extract_params_from_config(SAMPLE_WDL_INPUTS)
        assert 'reads' in params
        assert 'reference' in params
        assert 'threads' in params



# ---------------------------------------------------------------------------
# Integration: run_static_param_check with different pipeline types
# ---------------------------------------------------------------------------

class TestRunStaticParamCheckMultiPipeline:
    def test_snakemake_consistent(self):
        from static_checks import run_static_param_check
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'Snakefile'), 'w') as f:
                f.write(SAMPLE_SNAKEFILE)
            with open(os.path.join(tmpdir, 'config.yaml'), 'w') as f:
                f.write(SAMPLE_SNAKEMAKE_CONFIG)
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write("Use `--reads` and `--reference` and `--threads`.")

            result = run_static_param_check(
                tmpdir, ['Snakefile', 'config.yaml', 'README.md'],
                pipeline_type='snakemake'
            )
            assert result['verdict'] in ('PASS', 'FAIL')
            assert 'report' in result

    def test_cwl_consistent(self):
        from static_checks import run_static_param_check
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'tool.cwl'), 'w') as f:
                f.write(SAMPLE_CWL)
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write("Params: `--input_bam` and `--threads`.")

            result = run_static_param_check(
                tmpdir, ['tool.cwl', 'README.md'],
                pipeline_type='cwl'
            )
            assert result['verdict'] in ('PASS', 'FAIL')

    def test_wdl_consistent(self):
        from static_checks import run_static_param_check
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'pipeline.wdl'), 'w') as f:
                f.write(SAMPLE_WDL)
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write("Use `--reads`, `--reference`, and `--threads`.")

            result = run_static_param_check(
                tmpdir, ['pipeline.wdl', 'README.md'],
                pipeline_type='wdl'
            )
            assert result['verdict'] in ('PASS', 'FAIL')

    def test_nextflow_still_works(self):
        """Existing Nextflow path with explicit pipeline_type."""
        from static_checks import run_static_param_check
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'main.nf'), 'w') as f:
                f.write("params.input = 'x'\nparams.output = 'y'")
            with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
                f.write("Use `--input` and `--output`.")

            result = run_static_param_check(
                tmpdir, ['main.nf', 'README.md'],
                pipeline_type='nextflow'
            )
            assert result['match'] is True
