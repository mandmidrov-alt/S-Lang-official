from pathlib import Path

from slang.backend import compile_program, lower_compiler_artifact
from slang.compiler_artifact import CompilerArtifact
from slang.core import parse_file


def _artifact():
    return compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native").artifact


def test_parameter_materialization_is_persisted_and_deterministic():
    artifact = _artifact()
    assert artifact.artifact_version == "7"
    assert artifact.parameter_materialization
    for binding, kind, canonical, seed in artifact.parameter_materialization:
        assert binding
        assert kind
        assert canonical.startswith("{")
        assert seed.isdigit()
        assert int(seed) < 2**63
    restored = CompilerArtifact.from_json(artifact.to_json())
    assert restored.parameter_materialization == artifact.parameter_materialization
    assert restored.fingerprint == artifact.fingerprint


def test_mlir_materializes_parameter_before_runtime_call():
    text = lower_compiler_artifact(_artifact(), backend="mlir").text
    assert "@slang_materialize_param" in text
    assert "operation-parameter-materialized" in text
    assert "@slang_reduce(%artifact_" in text


def test_parameter_materialization_tampering_is_rejected():
    import json
    manifest = json.loads(_artifact().to_json())
    manifest["parameter_materialization"][0][3] = "1"
    try:
        CompilerArtifact.from_manifest(manifest)
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("tampered parameter materialization was accepted")
