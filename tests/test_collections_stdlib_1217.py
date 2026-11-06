import pytest
from slang.stdlib.collections import l2_norm_numbers, euclidean_distance_numbers


def test_l2_norm_numbers():
    assert l2_norm_numbers([3, 4]) == 5.0
    assert l2_norm_numbers([]) == 0
    assert l2_norm_numbers([-3, 4]) == 5.0


def test_euclidean_distance_numbers():
    assert euclidean_distance_numbers([1, 2], [4, 6]) == 5.0
    assert euclidean_distance_numbers([], []) == 0
    assert euclidean_distance_numbers([-1, 2], [3, -1]) == 5.0


def test_numeric_validation():
    with pytest.raises(TypeError):
        l2_norm_numbers([1, True])
    with pytest.raises(TypeError):
        euclidean_distance_numbers([1, True], [2, 3])
    with pytest.raises(TypeError):
        euclidean_distance_numbers([1, 2], [3, False])
    with pytest.raises(ValueError):
        euclidean_distance_numbers([1, 2], [3])
