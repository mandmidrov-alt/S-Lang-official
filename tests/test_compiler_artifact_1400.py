from pathlib import Path
from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline, compiler_artifact
from slang.compiler_artifact import build_compiler_artifact


def _pipeline():
    return compile_semantic_pipeline(parse("""
data people:
    Alice age 20
    Bob age 16
adults = people where age >= 18
show adults
""").ast)


def test_compiler_artifact_is_deterministic():
    a = compiler_artifact(_pipeline())
    b = compiler_artifact(_pipeline())
    assert a.fingerprint == b.fingerprint
    assert a.to_json() == b.to_json()


def test_compiler_artifact_contains_backend_contracts():
    artifact = compiler_artifact(_pipeline())
    assert artifact.artifact_version == "7"
    assert artifact.type_contract
    assert artifact.strategy_contract
    assert artifact.effect_contract
    assert artifact.fingerprint


def test_compiler_artifact_roundtrip_manifest_is_json_safe():
    artifact = build_compiler_artifact(_pipeline())
    manifest = artifact.manifest()
    assert manifest["fingerprint"] == artifact.fingerprint
    assert manifest["artifact_version"] == "7"
    assert isinstance(artifact.to_json(), str)
    assert artifact.to_json().startswith('{')


def test_backend_compilation_exposes_the_same_compiler_artifact():
    from slang.backend import compile_program
    from slang.core import parse_file
    module = parse_file(Path("examples/fused_reduce.sl"))
    result = compile_program(module, backend="auto")
    assert result.artifact is not None
    assert result.artifact.fingerprint
    assert result.artifact.type_contract == tuple(result.decision.pipeline.optimized_ir.type_contract())


def test_compiler_artifact_v2_roundtrip_preserves_backend_payload():
    from slang.backend import compile_program
    from slang.compiler_artifact import CompilerArtifact
    from slang.core import parse_file

    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    restored = CompilerArtifact.from_json(result.artifact.to_json())
    assert restored.artifact_version == "7"
    assert restored.fingerprint == result.artifact.fingerprint
    assert restored.backend_ast().filters


def test_compiler_artifact_rejects_fingerprint_tampering():
    import json
    from slang.backend import compile_program
    from slang.compiler_artifact import CompilerArtifact
    from slang.core import parse_file

    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    manifest = json.loads(result.artifact.to_json())
    manifest["fingerprint"] = "0" * 64
    try:
        CompilerArtifact.from_manifest(manifest)
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("tampered compiler artifact was accepted")


def test_native_backend_can_lower_loaded_artifact_without_source_file():
    from slang.backend import compile_program, lower_compiler_artifact
    from slang.compiler_artifact import CompilerArtifact
    from slang.core import parse_file

    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    loaded = CompilerArtifact.from_json(result.artifact.to_json())
    lowered = lower_compiler_artifact(loaded, backend="native")
    assert lowered.format == "llvm-ir"
    assert lowered.executable is True
    assert "define" in lowered.text
    assert "selected-strategy" in lowered.text
