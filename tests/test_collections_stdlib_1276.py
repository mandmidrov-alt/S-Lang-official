import pytest

from slang.stdlib import index_by_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_index_by_values_indexes_by_computed_key():
    values = [{"id": 10, "name": "Ada"}, {"id": 20, "name": "Linus"}]
    result = index_by_values(values, lambda item: item["id"])
    assert result == {10: values[0], 20: values[1]}


def test_index_by_values_rejects_duplicate_keys_and_does_not_mutate_input():
    values = [{"id": 1}, {"id": 1}]
    original = list(values)
    with pytest.raises(ValueError, match="unique computed keys"):
        index_by_values(values, lambda item: item["id"])
    assert values == original


def test_index_by_values_rejects_non_callable_key():
    with pytest.raises(TypeError, match="callable key"):
        index_by_values([1, 2], "id")


def test_index_by_values_public_api():
    assert get("index_by_values") is not None
    assert "index_by_values" in signatures()
    assert any(entry["name"] == "index_by_values" for entry in entries())
