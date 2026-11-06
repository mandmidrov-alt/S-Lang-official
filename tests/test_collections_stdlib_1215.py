import pytest
from slang.stdlib.collections import quantile_number


def test_quantile_number():
    assert quantile_number([1, 2, 3, 4], 0) == 1
    assert quantile_number([1, 2, 3, 4], 0.5) == 2.5
    assert quantile_number([1, 2, 3, 4], 1) == 4
    assert quantile_number([5], 0.5) == 5


def test_quantile_number_validation():
    with pytest.raises(RuntimeError):
        quantile_number([], 0.5)
    with pytest.raises(ValueError):
        quantile_number([1, 2], -0.1)
    with pytest.raises(ValueError):
        quantile_number([1, 2], 1.1)
    with pytest.raises(TypeError):
        quantile_number([1, True], 0.5)
    with pytest.raises(TypeError):
        quantile_number([1, 2], True)
