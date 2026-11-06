import pytest
from slang.stdlib.collections import sum_squares_numbers, dot_product_numbers


def test_sum_squares_numbers():
    assert sum_squares_numbers([1, 2, 3]) == 14
    assert sum_squares_numbers([]) == 0
    assert sum_squares_numbers([-2, 3]) == 13


def test_dot_product_numbers():
    assert dot_product_numbers([1, 2, 3], [4, 5, 6]) == 32
    assert dot_product_numbers([], []) == 0
    assert dot_product_numbers([-1, 2], [3, 4]) == 5


def test_numeric_validation():
    with pytest.raises(TypeError):
        sum_squares_numbers([1, True])
    with pytest.raises(TypeError):
        dot_product_numbers([1, True], [2, 3])
    with pytest.raises(TypeError):
        dot_product_numbers([1, 2], [3, False])
    with pytest.raises(ValueError):
        dot_product_numbers([1, 2], [3])
