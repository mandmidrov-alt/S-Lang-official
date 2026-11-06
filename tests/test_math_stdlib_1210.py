import math
import pytest
from slang.stdlib.math import truncate_number, fraction_number, is_even_number, is_odd_number


def test_truncate_and_fraction():
    assert truncate_number(3.9) == 3.0
    assert truncate_number(-3.9) == -3.0
    assert fraction_number(3.75) == pytest.approx(0.75)
    assert fraction_number(-3.75) == pytest.approx(-0.75)


def test_parity():
    assert is_even_number(8.0) is True
    assert is_even_number(-8.0) is True
    assert is_odd_number(7.0) is True
    assert is_odd_number(-7.0) is True
    with pytest.raises(ValueError):
        is_even_number(2.5)
    with pytest.raises(ValueError):
        is_odd_number(math.inf)
