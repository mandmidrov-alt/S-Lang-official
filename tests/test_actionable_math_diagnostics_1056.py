import pytest

from slang.core import parse, run
from slang.stdlib.math import exp_number, exp2_number, pow_number, sqrt, log_number


def test_division_by_zero_has_actionable_message_in_reference_runtime():
    program = parse("let result = 10 / 0\nshow result\n")
    with pytest.raises((ZeroDivisionError, RuntimeError)) as caught:
        run(program)
    assert "divisor must be non-zero" in str(caught.value) or "division by zero" in str(caught.value)


def test_sqrt_and_log_domain_messages_name_expected_domain():
    with pytest.raises(ValueError, match="non-negative Number"):
        sqrt(-1)
    with pytest.raises(ValueError, match="positive value"):
        log_number(0)


def test_power_domain_error_explains_common_cause():
    with pytest.raises(ValueError, match="negative base with a fractional exponent"):
        pow_number(-2, 0.5)


def test_exponential_overflow_names_function_and_input():
    with pytest.raises(OverflowError, match="exp_number.*numeric range.*10000"):
        exp_number(10000)
    with pytest.raises(OverflowError, match="exp2_number.*numeric range.*10000"):
        exp2_number(10000)
