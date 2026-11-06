import pytest

from slang.stdlib.collections import argmax_number, argmin_number


def test_argmin_and_argmax_return_first_matching_index():
    assert argmin_number([4, 2, 2, 5]) == 1
    assert argmax_number([4, 7, 7, 3]) == 1
    assert argmin_number([-3]) == 0
    assert argmax_number([-3]) == 0


def test_argmin_and_argmax_reject_invalid_contracts():
    with pytest.raises(RuntimeError):
        argmin_number([])
    with pytest.raises(RuntimeError):
        argmax_number([])
    with pytest.raises(TypeError):
        argmin_number([1, True])
    with pytest.raises(TypeError):
        argmax_number([False, 2])
