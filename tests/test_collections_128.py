import math

from slang.stdlib.collections import variance_number, stddev_number


def test_numeric_dispersion():
    values = [1, 2, 3, 4, 5]
    assert variance_number(values) == 2.0
    assert stddev_number(values) == math.sqrt(2.0)
    assert variance_number([7, 7, 7]) == 0


def test_numeric_dispersion_validation():
    for fn in (variance_number, stddev_number):
        try:
            fn([])
            assert False
        except RuntimeError:
            pass
        try:
            fn([1, True])
            assert False
        except TypeError:
            pass
