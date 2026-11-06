from slang.core import parse, parse_expr, run, show_expr_value, validate
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER
import pytest


def test_inverse_trig_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('asin_number(0)'), env) == NUMBER
    assert infer(parse_expr('acos_number(1)'), env) == NUMBER
    assert infer(parse_expr('atan_number(1)'), env) == NUMBER
    assert infer(parse_expr('atan2_number(1, 0)'), env) == NUMBER


def test_inverse_trig_runtime():
    p = parse('''let a = asin_number(0)\nlet b = acos_number(1)\nlet c = atan_number(1)\nlet d = atan2_number(1, 0)\nshow a\nshow b\nshow c\nshow d\n''')
    validate(p); run(p)
    values = [show_expr_value(p, x) for x in p.show_exprs]
    assert [float(v) for v in values] == pytest.approx([0.0, 0.0, 0.7853981633974483, 1.5707963267948966], rel=1e-12)


def test_inverse_trig_domain_validation():
    for src in ('asin_number(2)', 'acos_number(0 - 2)'):
        p = parse(f'let x = {src}\nshow x\n')
        validate(p)
        try:
            run(p)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError('expected inverse-trigonometric domain failure')
