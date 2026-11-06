from pathlib import Path
from slang.backend import compile_program, lower_compiler_artifact
from slang.compiler_artifact import CompilerArtifact
from slang.core import parse_file


def _artifact():
    return compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native").artifact


def test_operation_contract_is_persisted_and_roundtrips():
    artifact = _artifact()
    assert artifact.artifact_version == "7"
    assert artifact.operation_contract
    kinds = {kind for _, kind, _ in artifact.operation_contract}
    assert "reduce" in kinds
    restored = CompilerArtifact.from_json(artifact.to_json())
    assert restored.operation_contract == artifact.operation_contract
    assert restored.fingerprint == artifact.fingerprint


def test_artifact_mlir_passes_parameter_slot_to_runtime_abi():
    artifact = _artifact()
    text = lower_compiler_artifact(artifact, backend="mlir").text
    assert "@slang_reduce(%artifact_" in text
    assert "(i64, i64) -> i64" in text
    assert "operation-parameter-materialized" in text


def test_operation_contract_tampering_is_rejected():
    import json
    manifest = json.loads(_artifact().to_json())
    manifest["operation_contract"][0][2] = {"tampered": True}
    try:
        CompilerArtifact.from_manifest(manifest)
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("tampered operation contract was accepted")
