import pytest
from slang.stdlib.collections import moving_average_numbers, normalize_numbers


def test_moving_average_numbers():
    assert moving_average_numbers([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]
    assert moving_average_numbers([1, 2, 3, 4], 3) == [2.0, 3.0]
    assert moving_average_numbers([1, 2], 3) == []
    assert moving_average_numbers([], 2) == []


def test_moving_average_validation():
    with pytest.raises(ValueError):
        moving_average_numbers([1, 2], 0)
    with pytest.raises(ValueError):
        moving_average_numbers([1, 2], -1)
    with pytest.raises(TypeError):
        moving_average_numbers([1, True], 2)
    with pytest.raises(TypeError):
        moving_average_numbers([1, 2], True)


def test_normalize_numbers():
    assert normalize_numbers([10, 20, 30]) == [0.0, 0.5, 1.0]
    assert normalize_numbers([]) == []
    assert normalize_numbers([5, 5, 5]) == [0.0, 0.0, 0.0]


def test_normalize_validation():
    with pytest.raises(TypeError):
        normalize_numbers([1, False])
