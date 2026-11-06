import math
import pytest

from slang.stdlib import math as slang_math


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True),
        (2, True),
        (-7, True),
        (2.0, True),
        (-3.0, True),
        (2.5, False),
        (float("inf"), False),
        (float("-inf"), False),
        (float("nan"), False),
        (True, False),
        (False, False),
        ("2", False),
        (None, False),
    ],
)
def test_is_integer_number_handles_python_numeric_types(value, expected):
    assert slang_math.is_integer_number(value) is expected


def test_integer_math_accepts_python_int_and_float_values():
    assert slang_math.gcd_number(12, 8) == 4.0
    assert slang_math.gcd_number(12.0, 8.0) == 4.0
    assert slang_math.lcm_number(12, 8) == 24.0
    assert slang_math.lcm_number(12.0, 8.0) == 24.0
    assert slang_math.factorial_number(5) == 120.0
    assert slang_math.factorial_number(5.0) == 120.0


@pytest.mark.parametrize("value", [True, False, 2.5, float("inf"), float("nan")])
def test_integer_math_rejects_non_integer_values(value):
    with pytest.raises(ValueError):
        slang_math.gcd_number(value, 2)
    with pytest.raises(ValueError):
        slang_math.lcm_number(2, value)
    with pytest.raises(ValueError):
        slang_math.factorial_number(value)


def test_parity_predicates_accept_int_and_integral_float():
    assert slang_math.is_even_number(4) is True
    assert slang_math.is_even_number(4.0) is True
    assert slang_math.is_odd_number(5) is True
    assert slang_math.is_odd_number(5.0) is True


def test_parity_predicates_reject_non_integer_values():
    with pytest.raises(ValueError):
        slang_math.is_even_number(2.5)
    with pytest.raises(ValueError):
        slang_math.is_odd_number(float("nan"))
