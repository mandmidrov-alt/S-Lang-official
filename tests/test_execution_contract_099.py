from pathlib import Path

from slang.backend import compile_program
from slang.core import parse_file, validate
from slang.execution_contract import format_execution_contract

ROOT = Path(__file__).resolve().parents[1]


def _module(name="fused_reduce.sl"):
    module = parse_file(ROOT / "examples" / name)
    validate(module)
    return module


def test_compilation_decision_contains_unified_execution_contract():
    result = compile_program(_module(), "native")
    contract = result.decision.execution_contract
    assert contract is not None
    assert "filter" in contract.operations
    assert "map" in contract.operations
    assert "reduce" in contract.operations
    assert "fused-filter-map-reduce" in contract.strategies
    assert contract.ordering == "source-order"
    assert "strategy:fused-filter-map-reduce" in contract.requirements
    assert "memory:scalar-accumulator" in contract.requirements


def test_execution_contract_is_deterministic_and_reportable():
    a = compile_program(_module(), "native").decision.execution_contract
    b = compile_program(_module(), "native").decision.execution_contract
    assert a == b
    text = format_execution_contract(a)
    assert text.startswith("execution.contract {")
    assert "materialization =" in text
