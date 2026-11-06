import pytest

from slang.stdlib.collections import covariance_numbers, correlation_numbers


def test_covariance_numbers():
    assert covariance_numbers([1, 2, 3], [2, 4, 6]) == pytest.approx(4 / 3)
    assert covariance_numbers([1, 2, 3], [3, 2, 1]) == pytest.approx(-2 / 3)


def test_correlation_numbers():
    assert correlation_numbers([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert correlation_numbers([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_covariance_and_correlation_reject_invalid_inputs():
    with pytest.raises(ValueError):
        covariance_numbers([], [])
    with pytest.raises(ValueError):
        covariance_numbers([1], [1, 2])
    with pytest.raises(ValueError):
        correlation_numbers([1, 1], [1, 2])
    with pytest.raises(TypeError):
        covariance_numbers([1, True], [1, 2])
    with pytest.raises(TypeError):
        correlation_numbers([1, 2], [1, False])
