from slang.stdlib import aggregate_values_by
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_aggregate_values_by_groups_and_aggregates():
    values = [1, 2, 3, 4, 5]
    assert aggregate_values_by(values, lambda x: x % 2, sum) == {1: 9, 0: 6}


def test_aggregate_values_by_preserves_key_order_and_input():
    values = [3, 1, 4, 2]
    snapshot = list(values)
    result = aggregate_values_by(values, lambda x: x % 2, lambda group: tuple(group))
    assert result == {1: (3, 1), 0: (4, 2)}
    assert values == snapshot


def test_aggregate_values_by_validates_callables():
    try:
        aggregate_values_by([1], 1, sum)
        assert False
    except TypeError:
        pass
    try:
        aggregate_values_by([1], lambda x: x, 1)
        assert False
    except TypeError:
        pass


def test_aggregate_values_by_public_api():
    assert get("aggregate_values_by") is not None
    assert "aggregate_values_by" in signatures()
    assert any(e["name"] == "aggregate_values_by" for e in entries())
