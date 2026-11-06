from pathlib import Path
from slang.backend import compile_program, lower_backend_artifact
from slang.compiler_artifact import CompilerArtifact
from slang.core import parse_file


def test_unified_backend_artifact_entrypoint_native():
    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    loaded = CompilerArtifact.from_json(result.artifact.to_json())
    lowered = lower_backend_artifact(loaded, backend="native")
    assert lowered.format == "llvm-ir"
    assert lowered.executable is True
    assert "define" in lowered.text


def test_unified_backend_artifact_entrypoint_mlir_without_source_recompile():
    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    loaded = CompilerArtifact.from_json(result.artifact.to_json())
    lowered = lower_backend_artifact(loaded, backend="mlir")
    assert lowered.format == "mlir"
    assert "slang.compiler_artifact" in lowered.text
    assert "artifact-node" in lowered.text
    assert loaded.fingerprint in lowered.text


def test_mlir_artifact_lowering_is_deterministic():
    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    loaded = CompilerArtifact.from_json(result.artifact.to_json())
    a = lower_backend_artifact(loaded, backend="mlir").text
    b = lower_backend_artifact(loaded, backend="mlir").text
    assert a == b
