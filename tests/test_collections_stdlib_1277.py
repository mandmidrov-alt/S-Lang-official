import pytest

from slang.stdlib import distinct_by_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_distinct_by_values_keeps_first_value_for_each_key():
    values = [{"id": 1, "kind": "a"}, {"id": 2, "kind": "b"}, {"id": 3, "kind": "a"}]
    result = distinct_by_values(values, lambda item: item["kind"])
    assert result == [values[0], values[1]]


def test_distinct_by_values_preserves_order_and_does_not_mutate_input():
    values = [3, 1, 4, 2, 6]
    original = list(values)
    assert distinct_by_values(values, lambda value: value % 2) == [3, 4]
    assert values == original


def test_distinct_by_values_rejects_non_callable_key():
    with pytest.raises(TypeError, match="callable key"):
        distinct_by_values([1, 2], "id")


def test_distinct_by_values_public_api():
    assert get("distinct_by_values") is not None
    assert "distinct_by_values" in signatures()
    assert any(entry["name"] == "distinct_by_values" for entry in entries())
