from slang.stdlib.collections import union_values


def test_union_values_preserves_first_seen_order_and_removes_duplicates():
    assert union_values([3, 1, 3, 2], [2, 4, 1, 5]) == [3, 1, 2, 4, 5]


def test_union_values_handles_empty_inputs():
    assert union_values([], [1, 2]) == [1, 2]
    assert union_values([1, 2], []) == [1, 2]


def test_union_values_does_not_mutate_inputs():
    left = [1, 2, 2]
    right = [2, 3]
    assert union_values(left, right) == [1, 2, 3]
    assert left == [1, 2, 2]
    assert right == [2, 3]
