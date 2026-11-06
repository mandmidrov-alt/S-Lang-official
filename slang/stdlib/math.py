from __future__ import annotations
import math


def abs_number(value: float) -> float:
    return abs(value)


def sqrt(value: float) -> float:
    if value < 0:
        raise ValueError("sqrt expects a non-negative Number")
    return math.sqrt(value)


def floor(value: float) -> int:
    return math.floor(value)


def truncate_number(value: float) -> float:
    """Remove the fractional part, rounding toward zero."""
    return float(math.trunc(value))


def fraction_number(value: float) -> float:
    """Return the signed fractional part of a Number."""
    return value - math.trunc(value)


def is_even_number(value: float) -> bool:
    if not is_integer_number(value):
        raise ValueError("is_even_number expects an integer-valued Number")
    return int(value) % 2 == 0


def is_odd_number(value: float) -> bool:
    if not is_integer_number(value):
        raise ValueError("is_odd_number expects an integer-valued Number")
    return int(value) % 2 != 0


def ceil(value: float) -> int:
    return math.ceil(value)


def round_number(value: float) -> int:
    return round(value)


def clamp_number(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ValueError("clamp_number expects minimum <= maximum")
    return min(max(value, minimum), maximum)


def sign_number(value: float) -> float:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def pow_number(value: float, exponent: float) -> float:
    try:
        return math.pow(value, exponent)
    except ValueError as exc:
        raise ValueError(
            f"pow_number cannot calculate {value} raised to {exponent}; "
            "check for a negative base with a fractional exponent or an invalid numeric value"
        ) from exc
    except OverflowError as exc:
        raise OverflowError(
            f"pow_number result is outside the supported numeric range for {value} raised to {exponent}"
        ) from exc


def min_of_numbers(left: float, right: float) -> float:
    return min(left, right)


def max_of_numbers(left: float, right: float) -> float:
    return max(left, right)


def lerp_number(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def log_number(value: float, base: float = math.e) -> float:
    if value <= 0:
        raise ValueError("log_number expects a positive value")
    if base <= 0 or base == 1:
        raise ValueError("log_number expects a positive base different from 1")
    return math.log(value, base)


def exp_number(value: float) -> float:
    try:
        return math.exp(value)
    except OverflowError as exc:
        raise OverflowError(
            f"exp_number result is outside the supported numeric range for input {value}"
        ) from exc


def exp2_number(value: float) -> float:
    try:
        return math.pow(2, value)
    except OverflowError as exc:
        raise OverflowError(
            f"exp2_number result is outside the supported numeric range for input {value}"
        ) from exc


def cbrt_number(value: float) -> float:
    if value == 0:
        return 0.0
    return math.copysign(abs(value) ** (1.0 / 3.0), value)


def log10_number(value: float) -> float:
    if value <= 0:
        raise ValueError("log10_number expects a positive value")
    return math.log10(value)


def log2_number(value: float) -> float:
    if value <= 0:
        raise ValueError("log2_number expects a positive value")
    return math.log2(value)


def mod_number(value: float, divisor: float) -> float:
    if divisor == 0:
        raise ValueError("mod_number expects a non-zero divisor")
    return value % divisor


def hypot_number(x: float, y: float) -> float:
    return math.hypot(x, y)


def degrees_number(value: float) -> float:
    return math.degrees(value)


def radians_number(value: float) -> float:
    return math.radians(value)


def sin_number(value: float) -> float:
    return math.sin(value)


def cos_number(value: float) -> float:
    return math.cos(value)


def tan_number(value: float) -> float:
    return math.tan(value)


def is_finite_number(value: float) -> bool:
    return math.isfinite(value)


def is_nan_number(value: float) -> bool:
    return math.isnan(value)


def is_integer_number(value: float) -> bool:
    """Return whether value is a finite integer-valued numeric scalar.

    bool is deliberately excluded even though bool subclasses int in Python.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer()
    return False


def reciprocal_number(value: float) -> float:
    if value == 0:
        raise ValueError("reciprocal_number expects a non-zero value")
    return 1 / value


def asin_number(value: float) -> float:
    if value < -1 or value > 1:
        raise ValueError("asin_number expects a value in [-1, 1]")
    return math.asin(value)


def acos_number(value: float) -> float:
    if value < -1 or value > 1:
        raise ValueError("acos_number expects a value in [-1, 1]")
    return math.acos(value)


def atan_number(value: float) -> float:
    return math.atan(value)


def atan2_number(y: float, x: float) -> float:
    return math.atan2(y, x)


def sinh_number(value: float) -> float:
    try:
        return math.sinh(value)
    except OverflowError as exc:
        raise OverflowError(
            f"sinh_number result is outside the supported numeric range for input {value}"
        ) from exc


def cosh_number(value: float) -> float:
    try:
        return math.cosh(value)
    except OverflowError as exc:
        raise OverflowError(
            f"cosh_number result is outside the supported numeric range for input {value}"
        ) from exc


def tanh_number(value: float) -> float:
    return math.tanh(value)


def asinh_number(value: float) -> float:
    return math.asinh(value)


def acosh_number(value: float) -> float:
    if value < 1:
        raise ValueError("acosh_number expects a value >= 1")
    return math.acosh(value)


def atanh_number(value: float) -> float:
    if value <= -1 or value >= 1:
        raise ValueError("atanh_number expects a value in (-1, 1)")
    return math.atanh(value)


def gcd_number(left: float, right: float) -> float:
    if not is_integer_number(left) or not is_integer_number(right):
        raise ValueError("gcd_number expects integer-valued Numbers")
    return float(math.gcd(int(left), int(right)))


def lcm_number(left: float, right: float) -> float:
    if not is_integer_number(left) or not is_integer_number(right):
        raise ValueError("lcm_number expects integer-valued Numbers")
    return float(math.lcm(int(left), int(right)))


def factorial_number(value: float) -> float:
    if not is_integer_number(value) or value < 0:
        raise ValueError("factorial_number expects a non-negative integer-valued Number")
    return float(math.factorial(int(value)))


def normalize_number(value: float, minimum: float, maximum: float) -> float:
    """Map a value from [minimum, maximum] to [0, 1]."""
    if minimum >= maximum:
        raise ValueError("normalize_number expects minimum < maximum")
    return (value - minimum) / (maximum - minimum)


def remap_number(value: float, source_minimum: float, source_maximum: float, target_minimum: float, target_maximum: float) -> float:
    """Map a value linearly from one numeric interval to another."""
    if source_minimum >= source_maximum:
        raise ValueError("remap_number expects source_minimum < source_maximum")
    return target_minimum + ((value - source_minimum) / (source_maximum - source_minimum)) * (target_maximum - target_minimum)
