from dataclasses import replace
from pathlib import Path

import pytest

from slang.backend import (
    BackendCapabilities,
    compile_selected_backend,
    native_capabilities,
    validate_execution_contract,
    validate_contract_closure,
    lowering_contract_for_pipeline,
)
from slang.core import parse_file, validate
from slang.execution_contract import build_execution_contract
from slang.compiler_pipeline import compile_semantic_pipeline

ROOT = Path(__file__).resolve().parents[1]


def _module(name="fused_reduce.sl"):
    module = parse_file(ROOT / "examples" / name)
    validate(module)
    return module


def test_native_capabilities_honor_fused_execution_contract():
    module = _module()
    caps = native_capabilities()
    pipeline = compile_semantic_pipeline(module.ast, caps.supported_strategies)
    contract = build_execution_contract(pipeline)
    assert caps.supports_execution_contract(contract) == ()
    validate_execution_contract(contract, caps)


def test_backend_rejects_contract_with_unsupported_parallelism():
    module = _module()
    caps = native_capabilities()
    pipeline = compile_semantic_pipeline(module.ast, caps.supported_strategies)
    contract = replace(build_execution_contract(pipeline), parallelism="parallel-where-independent")
    reasons = caps.supports_execution_contract(contract)
    assert "unsupported-parallelism=parallel-where-independent" in reasons
    with pytest.raises(ValueError, match="cannot honor execution contract"):
        validate_execution_contract(contract, caps)


def test_compilation_decision_validates_final_contract():
    decision = compile_selected_backend(_module().ast, "native")
    assert decision.execution_contract is not None
    assert decision.lowering_contract is not None


def test_contract_closure_requires_operation_lowerers():
    module = _module()
    caps = native_capabilities()
    pipeline = compile_semantic_pipeline(module.ast, caps.supported_strategies)
    execution = build_execution_contract(pipeline)
    lowering = lowering_contract_for_pipeline(pipeline, "native")
    from dataclasses import replace
    broken = replace(lowering, operation_lowerers=tuple(x for x in lowering.operation_lowerers if x[0] != "reduce"))
    with pytest.raises(ValueError, match="no operation lowerer"):
        validate_contract_closure(execution, broken, caps)


def test_contract_closure_requires_declared_runtime_features():
    module = _module()
    caps = native_capabilities()
    pipeline = compile_semantic_pipeline(module.ast, caps.supported_strategies)
    execution = build_execution_contract(pipeline)
    lowering = lowering_contract_for_pipeline(pipeline, "native")
    from dataclasses import replace
    broken = replace(lowering, runtime_features=("missing-runtime",))
    with pytest.raises(ValueError, match="does not advertise required runtime feature"):
        validate_contract_closure(execution, broken, caps)


def test_contract_closure_accepts_complete_native_contract():
    module = _module()
    caps = native_capabilities()
    pipeline = compile_semantic_pipeline(module.ast, caps.supported_strategies)
    execution = build_execution_contract(pipeline)
    lowering = lowering_contract_for_pipeline(pipeline, "native")
    validate_contract_closure(execution, lowering, caps)
