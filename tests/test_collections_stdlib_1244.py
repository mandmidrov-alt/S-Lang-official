from slang.stdlib.collections import zip_values


def test_zip_values_pairs_to_shorter_length():
    assert zip_values([1, 2, 3], ["a", "b"]) == [[1, "a"], [2, "b"]]


def test_zip_values_empty_and_equal_lengths():
    assert zip_values([], [1, 2]) == []
    assert zip_values([1, 2], [3, 4]) == [[1, 3], [2, 4]]


def test_zip_values_does_not_mutate_inputs():
    left = [1, 2]
    right = [3, 4]
    result = zip_values(left, right)
    assert left == [1, 2]
    assert right == [3, 4]
    assert result == [[1, 3], [2, 4]]
