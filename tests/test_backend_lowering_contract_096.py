from slang.backend import compile_selected_backend, lowering_contract_for, validate_lowering_contract
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.core import parse_file, validate


def load(name):
    p = parse_file(name)
    validate(p)
    return p.ast


def test_native_contract_is_attached_to_compilation_decision():
    decision = compile_selected_backend(load("examples/fused_reduce.sl"))
    assert decision.lowering_contract is not None
    assert decision.lowering_contract.backend == "native-llvm"
    assert decision.lowering_contract.lowerer_for_strategy("fused-filter-map-reduce") == "native.fused-filter-map-reduce"


def test_mlir_contract_contains_semantic_paths():
    contract = lowering_contract_for("mlir")
    assert contract.lowerer_for_strategy("physics-backend") == "mlir.slang.simulate_gravity"
    assert contract.lowerer_for_operation("filter") == "mlir.slang.filter"


def test_selected_pipeline_is_contract_validated():
    module = load("examples/fused_reduce.sl")
    pipeline = compile_semantic_pipeline(module, ("generic", "scan-filter", "sequential-map", "sequential-reduce", "fused-filter-map-reduce"))
    validate_lowering_contract(pipeline, lowering_contract_for("native"))
