import json
from pathlib import Path
from slang.core import parse_file
from slang.compiler_pipeline import compile_semantic_pipeline, compiler_artifact
from slang.compiler_artifact import CompilerArtifact
from slang.backend import lower_backend_artifact, compile_program


def _artifact():
    module = parse_file(Path("examples/fused_reduce.sl"))
    result = compile_program(module, backend="native")
    return result.artifact, result.decision.pipeline


def test_selected_execution_plan_round_trip():
    artifact, pipeline = _artifact()
    loaded = CompilerArtifact.from_json(artifact.to_json())
    assert loaded.fingerprint == artifact.fingerprint
    assert loaded.selected_execution_plan == artifact.selected_execution_plan
    assert len(loaded.selected_execution_plan["steps"]) == pipeline.selected_execution_plan.operation_count
    assert loaded.selected_execution_plan["execution_regions"]


def test_selected_plan_is_fingerprint_bound():
    artifact, _ = _artifact()
    manifest = artifact.manifest()
    manifest["selected_execution_plan"]["steps"][0]["strategy"] = "tampered"
    try:
        CompilerArtifact.from_manifest(manifest)
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("tampered selected execution plan was accepted")


def test_mlir_uses_persisted_selected_plan():
    artifact, _ = _artifact()
    text = lower_backend_artifact(CompilerArtifact.from_json(artifact.to_json()), backend="mlir").text
    assert "selected-region=" in text
    assert "segment_mode=" in text
    assert artifact.fingerprint in text
