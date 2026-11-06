from pathlib import Path

from slang.backend import compile_selected_backend, lower_compilation_decision
from slang.core import parse_file, validate

ROOT = Path(__file__).resolve().parents[1]


def _module(name="fused_reduce.sl"):
    p = parse_file(ROOT / "examples" / name)
    validate(p)
    return p


def test_native_dispatcher_uses_selected_contract():
    module = _module()
    decision = compile_selected_backend(module.ast, "auto")
    lowered = lower_compilation_decision(module, decision)
    assert lowered.backend == "native-llvm"
    assert lowered.strategy == "fused-filter-map-reduce"
    assert lowered.lowerer == "native.fused-filter-map-reduce"
    assert lowered.format == "llvm-ir"
    assert "selected-strategy = fused-filter-map-reduce" in lowered.text


def test_dispatcher_rejects_missing_contract():
    module = _module()
    decision = compile_selected_backend(module.ast, "native")
    broken = type(decision)(
        backend=decision.backend,
        selection=decision.selection,
        pipeline=decision.pipeline,
        artifact=decision.artifact,
        lowering_contract=None,
    )
    try:
        lower_compilation_decision(module, broken)
    except ValueError as exc:
        assert "no lowering contract" in str(exc)
    else:
        raise AssertionError("expected missing lowering contract error")
