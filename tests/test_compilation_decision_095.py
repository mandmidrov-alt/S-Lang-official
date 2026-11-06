from pathlib import Path

from slang.backend import compile_selected_backend
from slang.core import parse_file, validate

ROOT = Path(__file__).resolve().parents[1]


def _module(name="fused_reduce.sl"):
    p = parse_file(ROOT / "examples" / name)
    validate(p)
    return p.ast


def test_auto_compilation_decision_selects_native_when_ready():
    decision = compile_selected_backend(_module(), "auto")
    assert decision.backend == "native-llvm"
    assert decision.artifact.backend == decision.backend
    assert decision.selection.selected == decision.backend
    assert decision.pipeline.strategies


def test_explicit_native_uses_same_capability_validation_path():
    decision = compile_selected_backend(_module(), "native")
    assert decision.backend == "native-llvm"
    assert len(decision.selection.candidates) == 1
    assert decision.selection.candidates[0].compatible


def test_compilation_decision_rejects_incompatible_mlir_data_program():
    try:
        compile_selected_backend(_module(), "mlir")
    except ValueError as exc:
        text = str(exc)
        assert "not compatible" in text
    else:
        raise AssertionError("expected incompatible MLIR decision")
