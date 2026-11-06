from pathlib import Path

from slang.backend import compile_program
from slang.core import parse_file, validate


def load(name):
    p = parse_file(Path(name))
    validate(p)
    return p


def test_unified_compile_runs_plan_selection_and_lowering():
    module = load("examples/fused_reduce.sl")
    result = compile_program(module, "auto")
    assert result.decision.backend == "native-llvm"
    assert result.lowered.backend == "native-llvm"
    assert result.lowered.format == "llvm-ir"
    assert result.lowered.lowerer == "native.fused-filter-map-reduce"
    assert result.decision.lowering_contract is not None


def test_unified_compile_matches_explicit_native():
    module = load("examples/fused_reduce.sl")
    result = compile_program(module, "native")
    assert result.decision.backend == "native-llvm"
    assert "define" in result.lowered.text
