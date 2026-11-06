from slang.stdlib.collections import concat_values


def test_concat_values_preserves_order():
    assert concat_values([1, 2], [3, 4]) == [1, 2, 3, 4]


def test_concat_values_handles_empty_inputs():
    assert concat_values([], [1, 2]) == [1, 2]
    assert concat_values([1, 2], []) == [1, 2]


def test_concat_values_does_not_mutate_inputs():
    left = [1, 2]
    right = [3]
    result = concat_values(left, right)
    result.append(4)
    assert left == [1, 2]
    assert right == [3]
