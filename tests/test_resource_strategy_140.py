from slang.cost_model import resource_profile, choose_by_cost
from slang.execution_ir import ExecutionNode, DataShape
from slang.strategy_selection import select_strategy


def node(kind="map", n=10, parallel_safe=True):
    return ExecutionNode("x", kind, "r", (), (), True, deterministic=True, data_shape=DataShape(n,n,True,(),"linear","test"), order_sensitive=not parallel_safe)


def test_resource_profiles_are_explicit():
    assert resource_profile("sequential-map") == ("linear-buffer", "source-order", "sequential")
    assert resource_profile("parallel-map") == ("linear-buffer", "dependency-ordered", "parallel-where-independent")
    assert resource_profile("fused-filter-map-reduce") == ("scalar-accumulator", "source-order", "sequential")


def test_backend_parallelism_filters_parallel_strategy():
    choice = select_strategy(node(n=100), allowed_strategies=("sequential-map", "parallel-map"), backend_memory_models=("linear-buffer",), backend_orderings=("source-order",), backend_parallelism=("sequential",))
    assert choice.strategy == "sequential-map"


def test_backend_memory_model_filters_fused_strategy():
    choice = select_strategy(node("map", n=100), allowed_strategies=("sequential-map", "fused-filter-map-reduce"), backend_memory_models=("linear-buffer",), backend_orderings=("source-order",), backend_parallelism=("sequential",))
    assert choice.strategy == "sequential-map"


def test_cost_estimates_expose_resources():
    decision = choose_by_cost(node(n=100), ("sequential-map", "parallel-map"))
    estimates = {e.strategy: e for e in decision.estimates}
    assert estimates["sequential-map"].memory == "linear-buffer"
    assert estimates["parallel-map"].parallelism_mode == "parallel-where-independent"
    assert estimates["parallel-map"].ordering == "dependency-ordered"
