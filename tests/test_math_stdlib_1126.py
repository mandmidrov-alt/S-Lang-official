from slang.core import parse, parse_expr, run, show_expr_value, validate
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER
import pytest


def test_integer_math_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('gcd_number(12, 8)'), env) == NUMBER
    assert infer(parse_expr('lcm_number(12, 8)'), env) == NUMBER
    assert infer(parse_expr('factorial_number(5)'), env) == NUMBER


def test_integer_math_runtime():
    p = parse('''let a = gcd_number(12, 8)\nlet b = lcm_number(12, 8)\nlet c = factorial_number(5)\nshow a\nshow b\nshow c\n''')
    validate(p); run(p)
    values = [float(show_expr_value(p, x)) for x in p.show_exprs]
    assert values == pytest.approx([4.0, 24.0, 120.0])


def test_integer_math_validation():
    cases = (
        'gcd_number(2.5, 4)',
        'lcm_number(2, 4.5)',
        'factorial_number(0 - 1)',
        'factorial_number(2.5)',
    )
    for src in cases:
        p = parse(f'let x = {src}\nshow x\n')
        validate(p)
        with pytest.raises((ValueError, RuntimeError)):
            run(p)
