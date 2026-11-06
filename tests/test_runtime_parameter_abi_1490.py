from slang.compiler_artifact import build_compiler_artifact
from slang.compiler_pipeline import CompilerPipeline
from slang.runtime_parameter_abi import build_runtime_parameter_table, validate_runtime_parameter
from slang.mlir_backend import lower_compiler_artifact_to_mlir
from pathlib import Path
from slang.core import parse_file


def _artifact():
    return __import__('slang.backend', fromlist=['compile_program']).compile_program(parse_file(Path('examples/fused_reduce.sl')), backend='native').artifact


def test_runtime_descriptor_table_matches_artifact():
    artifact = _artifact()
    table = build_runtime_parameter_table(artifact)
    assert table
    for binding, desc in table.items():
        assert validate_runtime_parameter(artifact, binding).seed == desc.seed


def test_runtime_descriptor_rejects_size_tampering():
    artifact = _artifact()
    manifest = artifact.manifest()
    manifest["parameter_abi_descriptors"][0][3] += 1
    import pytest
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        type(artifact).from_manifest(manifest)


def test_runtime_descriptor_rejects_materialization_mismatch():
    artifact = _artifact()
    import dataclasses
    bad = dataclasses.replace(artifact, parameter_materialization=tuple((b,k,c,str(int(seed)+1)) for b,k,c,seed in artifact.parameter_materialization))
    import pytest
    with pytest.raises(ValueError, match="runtime parameter"):
        build_runtime_parameter_table(bad)


def test_mlir_emits_runtime_descriptor_metadata():
    artifact = _artifact()
    text = lower_compiler_artifact_to_mlir(artifact)
    assert "runtime-parameter-descriptor" in text
    assert "@slang_materialize_param" in text
