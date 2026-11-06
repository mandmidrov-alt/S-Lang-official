import pytest

from slang.stdlib import max_by_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_max_by_values_returns_value_with_largest_key():
    values = [{"name": "a", "score": 7}, {"name": "b", "score": 2}, {"name": "c", "score": 9}]
    assert max_by_values(values, lambda item: item["score"]) == values[2]


def test_max_by_values_keeps_first_value_on_tie():
    values = [{"name": "first", "score": 9}, {"name": "second", "score": 9}, {"name": "later", "score": 3}]
    assert max_by_values(values, lambda item: item["score"]) is values[0]


def test_max_by_values_rejects_invalid_inputs():
    with pytest.raises(TypeError, match="callable key"):
        max_by_values([1, 2], "id")
    with pytest.raises(ValueError, match="empty collection"):
        max_by_values([], lambda value: value)


def test_max_by_values_public_api():
    assert get("max_by_values") is not None
    assert "max_by_values" in signatures()
    assert any(entry["name"] == "max_by_values" for entry in entries())
