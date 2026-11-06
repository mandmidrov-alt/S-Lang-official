from slang.stdlib import aggregate_values_by_with_key
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_aggregate_values_by_with_key():
    values = [1, 2, 3, 4, 5]
    assert aggregate_values_by_with_key(
        values,
        lambda value: value % 2,
        lambda group_key, group: {"key": group_key, "sum": sum(group)},
    ) == {
        1: {"key": 1, "sum": 9},
        0: {"key": 0, "sum": 6},
    }


def test_aggregate_values_by_with_key_preserves_key_order_and_input():
    values = [4, 1, 2, 3]
    original = list(values)
    result = aggregate_values_by_with_key(
        values,
        lambda value: value % 2,
        lambda key, group: (key, list(group)),
    )
    assert list(result.keys()) == [0, 1]
    assert result[0] == (0, [4, 2])
    assert result[1] == (1, [1, 3])
    assert values == original


def test_aggregate_values_by_with_key_empty():
    assert aggregate_values_by_with_key([], lambda value: value, lambda key, group: (key, len(group))) == {}


def test_aggregate_values_by_with_key_rejects_non_callables():
    try:
        aggregate_values_by_with_key([1], "key", lambda key, group: group)
        assert False
    except TypeError as exc:
        assert "callable key" in str(exc)

    try:
        aggregate_values_by_with_key([1], lambda value: value, "aggregate")
        assert False
    except TypeError as exc:
        assert "callable aggregate" in str(exc)


def test_aggregate_values_by_with_key_public_api():
    assert get("aggregate_values_by_with_key") is not None
    assert "aggregate_values_by_with_key" in signatures()
    assert any(item["name"] == "aggregate_values_by_with_key" for item in entries())
