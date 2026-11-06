from pathlib import Path
from slang.core import parse_file
from slang.backend import compile_program, lower_backend_artifact
from slang.compiler_artifact import CompilerArtifact


def test_artifact_mlir_lowers_concrete_runtime_calls():
    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    artifact = CompilerArtifact.from_json(result.artifact.to_json())
    text = lower_backend_artifact(artifact, backend="mlir").text
    assert "func.call @slang_" in text
    assert "artifact-node" in text
    assert "selected-region=" in text
    assert artifact.fingerprint in text
    assert artifact.parameter_abi_descriptors
    assert "parameter-abi type=" in text


def test_artifact_mlir_is_deterministic_after_round_trip():
    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    artifact = CompilerArtifact.from_json(result.artifact.to_json())
    a = lower_backend_artifact(artifact, backend="mlir").text
    b = lower_backend_artifact(CompilerArtifact.from_json(artifact.to_json()), backend="mlir").text
    assert a == b
