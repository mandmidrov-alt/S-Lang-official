from slang.stdlib.collections import symmetric_difference_values

def test_symmetric_difference_values_preserves_first_seen_order():
    assert symmetric_difference_values([3, 1, 2, 2], [2, 4, 4, 1]) == [3, 4]

def test_symmetric_difference_values_handles_empty_inputs():
    assert symmetric_difference_values([], [1, 2]) == [1, 2]
    assert symmetric_difference_values([1, 2], []) == [1, 2]

def test_symmetric_difference_values_does_not_mutate_inputs():
    left = [1, 2, 2]
    right = [2, 3]
    assert symmetric_difference_values(left, right) == [1, 3]
    assert left == [1, 2, 2]
    assert right == [2, 3]
