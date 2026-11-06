from slang.core import parse, validate, run, show_expr_value


def evaluate(source: str) -> list[str]:
    program = parse(source)
    validate(program)
    run(program)
    return [show_expr_value(program, expr) for expr in program.show_exprs]


def test_multiplication_binds_more_tightly_than_addition():
    assert evaluate("show 2 + 3 * 4\n") == ["14"]


def test_power_is_right_associative():
    assert evaluate("show 2 ^ 3 ^ 2\n") == ["512"]


def test_parentheses_override_precedence():
    assert evaluate("show (2 + 3) * 4\n") == ["20"]
