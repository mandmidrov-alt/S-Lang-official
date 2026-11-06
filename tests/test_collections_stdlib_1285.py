from slang.stdlib import partition_by_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries
import pytest


def test_partition_by_values_groups_and_preserves_order():
    values = ["ant", "apple", "bee", "avocado"]
    assert partition_by_values(values, lambda x: x[0]) == {
        "a": ["ant", "apple", "avocado"],
        "b": ["bee"],
    }
    assert values == ["ant", "apple", "bee", "avocado"]


def test_partition_by_values_empty():
    assert partition_by_values([], lambda x: x) == {}


def test_partition_by_values_rejects_non_callable():
    with pytest.raises(TypeError, match="callable key"):
        partition_by_values([1, 2], 1)


def test_partition_by_values_public_api():
    assert get("partition_by_values") is not None
    assert "partition_by_values" in signatures()
    assert any(e["name"] == "partition_by_values" for e in entries())
