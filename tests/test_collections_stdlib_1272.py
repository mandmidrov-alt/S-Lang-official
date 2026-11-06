from slang.stdlib import sort_descending_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_sort_descending_values_orders_descending():
    assert sort_descending_values([5, 2, 4, 1, 3]) == [5, 4, 3, 2, 1]


def test_sort_descending_values_does_not_mutate():
    values = [3, 1, 2]
    assert sort_descending_values(values) == [3, 2, 1]
    assert values == [3, 1, 2]


def test_sort_descending_values_public_api():
    assert get("sort_descending_values") is not None
    assert "sort_descending_values" in signatures()
    assert any(e["name"] == "sort_descending_values" for e in entries())
