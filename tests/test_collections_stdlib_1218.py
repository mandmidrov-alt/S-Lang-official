import pytest
from slang.stdlib.collections import manhattan_distance_numbers, cosine_similarity_numbers


def test_manhattan_distance_numbers():
    assert manhattan_distance_numbers([1, 2], [4, 6]) == 7
    assert manhattan_distance_numbers([], []) == 0
    assert manhattan_distance_numbers([-1, 2], [3, -1]) == 7


def test_cosine_similarity_numbers():
    assert cosine_similarity_numbers([1, 0], [1, 0]) == 1.0
    assert cosine_similarity_numbers([1, 0], [0, 1]) == 0.0
    assert cosine_similarity_numbers([1, 1], [1, 1]) == pytest.approx(1.0)


def test_validation():
    with pytest.raises(TypeError):
        manhattan_distance_numbers([1, True], [2, 3])
    with pytest.raises(TypeError):
        cosine_similarity_numbers([1, 2], [3, False])
    with pytest.raises(ValueError):
        manhattan_distance_numbers([1, 2], [3])
    with pytest.raises(ValueError):
        cosine_similarity_numbers([0, 0], [1, 2])
    with pytest.raises(ValueError):
        cosine_similarity_numbers([1, 2], [0, 0])
