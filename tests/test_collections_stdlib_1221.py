import pytest

from slang.stdlib.collections import weighted_average_numbers


def test_weighted_average_numbers():
    assert weighted_average_numbers([10, 20, 30], [1, 2, 1]) == pytest.approx(20.0)
    assert weighted_average_numbers([1, 3], [3, 1]) == pytest.approx(1.5)


def test_weighted_average_numbers_rejects_invalid_contracts():
    with pytest.raises(RuntimeError):
        weighted_average_numbers([], [])
    with pytest.raises(ValueError):
        weighted_average_numbers([1, 2], [1])
    with pytest.raises(RuntimeError):
        weighted_average_numbers([1, 2], [1, -1])
    with pytest.raises(TypeError):
        weighted_average_numbers([1, True], [1, 2])
    with pytest.raises(TypeError):
        weighted_average_numbers([1, 2], [1, False])
