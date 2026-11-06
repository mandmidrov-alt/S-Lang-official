from slang.cost_model import choose_by_cost
from slang.execution_ir import ExecutionNode, DataShape
from slang.strategy_selection import select_strategy


def node(n=100):
    return ExecutionNode("x", "map", "r", (), (), True, deterministic=True,
                         data_shape=DataShape(n, n, True, (), "linear", "test"),
                         order_sensitive=False)


def test_backend_preferences_can_prioritize_memory():
    decision = choose_by_cost(
        node(),
        ("sequential-map", "fused-filter-map-reduce"),
        resource_preferences=(("memory", 100.0),),
    )
    assert decision.selected == "fused-filter-map-reduce"


def test_preferences_do_not_change_legal_candidates():
    choice = select_strategy(
        node(),
        allowed_strategies=("sequential-map", "parallel-map"),
        backend_memory_models=("linear-buffer",),
        backend_orderings=("source-order", "dependency-ordered"),
        backend_parallelism=("sequential", "parallel-where-independent"),
        backend_resource_preferences=(("parallelism", 200.0),),
    )
    assert choice.strategy == "sequential-map"


def test_preference_selection_is_deterministic():
    kwargs = dict(
        backend_resource_preferences=(("memory", 3.0), ("parallelism", 1.0)),
    )
    a = choose_by_cost(node(), ("sequential-map", "parallel-map"), resource_preferences=kwargs["backend_resource_preferences"])
    b = choose_by_cost(node(), ("sequential-map", "parallel-map"), resource_preferences=kwargs["backend_resource_preferences"])
    assert a == b
