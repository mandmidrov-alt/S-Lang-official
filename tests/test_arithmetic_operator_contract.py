"""Arithmetic parser contract: supported forms and explicit remaining limitations."""
import pytest

from slang.core import parse, validate, run, show_expr_value


def evaluate(source: str) -> list[str]:
    program = parse(source)
    validate(program)
    run(program)
    return [show_expr_value(program, expr) for expr in program.show_exprs]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("show 7 + 2\n", ["9"]),
        ("show 7 - 2\n", ["5"]),
        ("show 7 * 2\n", ["14"]),
        ("show 7 / 2\n", ["3.5"]),
        ("show 7 % 3\n", ["1"]),
        ("show -7 % 3\n", ["-1"]),
        ("show 7 % -3\n", ["1"]),
        ("show 2 ^ 3\n", ["8"]),
        ("show -5\n", ["-5"]),
        ("show +5\n", ["5"]),
        ("show -2 ^ 2\n", ["-4"]),
        ("show 2 ^ -2\n", ["0.25"]),
    ],
)
def test_supported_arithmetic_operators_in_interpreter(source, expected):
    assert evaluate(source) == expected


def test_modulo_by_zero_is_runtime_error():
    program = parse("show 7 % 0\n")
    validate(program)
    with pytest.raises(ZeroDivisionError, match="modulo by zero"):
        show_expr_value(program, program.show_exprs[0])
