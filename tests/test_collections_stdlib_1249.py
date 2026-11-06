from slang.stdlib.collections import intersect_values


def test_intersect_values_preserves_left_order_and_removes_duplicates():
    assert intersect_values([3, 1, 3, 2, 4], [2, 3, 5]) == [3, 2]


def test_intersect_values_handles_empty_inputs():
    assert intersect_values([], [1, 2]) == []
    assert intersect_values([1, 2], []) == []


def test_intersect_values_does_not_mutate_inputs():
    left = [1, 2, 3]
    right = [2, 3, 4]
    assert intersect_values(left, right) == [2, 3]
    assert left == [1, 2, 3]
    assert right == [2, 3, 4]
