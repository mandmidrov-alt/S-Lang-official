import pytest

from slang.stdlib import min_by_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_min_by_values_returns_value_with_smallest_key():
    values = [{"name": "a", "score": 7}, {"name": "b", "score": 2}, {"name": "c", "score": 5}]
    assert min_by_values(values, lambda item: item["score"]) == values[1]


def test_min_by_values_keeps_first_value_on_tie():
    values = [{"name": "first", "score": 1}, {"name": "second", "score": 1}, {"name": "later", "score": 3}]
    assert min_by_values(values, lambda item: item["score"]) is values[0]


def test_min_by_values_rejects_invalid_inputs():
    with pytest.raises(TypeError, match="callable key"):
        min_by_values([1, 2], "id")
    with pytest.raises(ValueError, match="empty collection"):
        min_by_values([], lambda value: value)


def test_min_by_values_public_api():
    assert get("min_by_values") is not None
    assert "min_by_values" in signatures()
    assert any(entry["name"] == "min_by_values" for entry in entries())
