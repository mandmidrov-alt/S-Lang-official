from slang.cost_model import materialization_profile
from slang.execution_ir import ExecutionNode, DataShape
from slang.strategy_selection import select_strategy


def node(n=100):
    return ExecutionNode("x", "map", "r", (), (), True, deterministic=True,
                         data_shape=DataShape(n, n, True, (), "linear", "test"),
                         order_sensitive=False)


def test_fused_strategies_require_streaming_materialization_support():
    choice = select_strategy(
        node(),
        fusion_strategies=("fused-filter-map-reduce",),
        allowed_strategies=("sequential-map", "fused-filter-map-reduce"),
        backend_memory_models=("linear-buffer", "scalar-accumulator"),
        backend_orderings=("source-order",),
        backend_parallelism=("sequential",),
        backend_materialization=("backend-defined",),
    )
    assert choice.strategy == "sequential-map"


def test_streaming_backend_allows_fused_strategy():
    assert materialization_profile("fused-filter-map-reduce") == "streaming-when-fused"
    choice = select_strategy(
        node(),
        fusion_strategies=("fused-filter-map-reduce",),
        allowed_strategies=("sequential-map", "fused-filter-map-reduce"),
        backend_memory_models=("linear-buffer", "scalar-accumulator"),
        backend_orderings=("source-order",),
        backend_parallelism=("sequential",),
        backend_materialization=("streaming-when-fused", "backend-defined"),
    )
    assert choice.strategy == "fused-filter-map-reduce"
