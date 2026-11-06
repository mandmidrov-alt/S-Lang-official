from slang.stdlib import group_by_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_group_by_values_groups_by_key():
    result = group_by_values(["apple", "apricot", "banana"], lambda value: value[0])
    assert result == {"a": ["apple", "apricot"], "b": ["banana"]}


def test_group_by_values_preserves_order_and_does_not_mutate():
    values = [1, 2, 3, 4]
    result = group_by_values(values, lambda value: value % 2)
    assert result == {1: [1, 3], 0: [2, 4]}
    assert values == [1, 2, 3, 4]


def test_group_by_values_public_api():
    assert get("group_by_values") is not None
    assert "group_by_values" in signatures()
    assert any(item["name"] == "group_by_values" for item in entries())
