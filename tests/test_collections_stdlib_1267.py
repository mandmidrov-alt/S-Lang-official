from slang.stdlib import split_at_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_split_at_values():
    assert split_at_values([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_split_at_values_boundaries():
    assert split_at_values([1, 2], 0) == [[], [1, 2]]
    assert split_at_values([1, 2], 99) == [[1, 2], []]
    assert split_at_values([1, 2], -5) == [[], [1, 2]]


def test_split_at_values_does_not_mutate():
    values = [1, 2, 3]
    split_at_values(values, 1)
    assert values == [1, 2, 3]


def test_split_at_values_public_api():
    assert get("split_at_values") is not None
    assert "split_at_values" in signatures()
    assert any(entry["name"] == "split_at_values" for entry in entries())
