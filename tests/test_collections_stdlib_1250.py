from slang.stdlib.collections import difference_values


def test_difference_values_preserves_left_order_and_removes_duplicates():
    assert difference_values([3, 1, 3, 2, 4], [2, 5]) == [3, 1, 4]


def test_difference_values_handles_empty_inputs():
    assert difference_values([], [1, 2]) == []
    assert difference_values([1, 2], []) == [1, 2]


def test_difference_values_does_not_mutate_inputs():
    left = [1, 2, 3]
    right = [2, 4]
    assert difference_values(left, right) == [1, 3]
    assert left == [1, 2, 3]
    assert right == [2, 4]
