from slang.stdlib.collections import unique_values


def test_unique_values_preserves_first_seen_order():
    assert unique_values([3, 1, 3, 2, 1, 2]) == [3, 1, 2]


def test_unique_values_supports_mixed_types_without_merging_types():
    assert unique_values([1, True, 1, True]) == [1, True]


def test_unique_values_handles_empty_input():
    assert unique_values([]) == []
