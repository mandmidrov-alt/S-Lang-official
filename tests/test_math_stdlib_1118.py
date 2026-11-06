from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER


def test_math_1118_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('mod_number(7, 3)'), env) == NUMBER
    assert infer(parse_expr('hypot_number(3, 4)'), env) == NUMBER
    assert infer(parse_expr('degrees_number(3.141592653589793)'), env) == NUMBER
    assert infer(parse_expr('radians_number(180)'), env) == NUMBER
    assert infer(parse_expr('sin_number(0)'), env) == NUMBER
    assert infer(parse_expr('cos_number(0)'), env) == NUMBER
    assert infer(parse_expr('tan_number(0)'), env) == NUMBER


def test_math_1118_runtime():
    source = '''let a = mod_number(7, 3)
let b = hypot_number(3, 4)
let c = degrees_number(3.141592653589793)
let d = radians_number(180)
let e = sin_number(0)
let f = cos_number(0)
let g = tan_number(0)
show a
show b
show c
show d
show e
show f
show g
'''
    p = parse(source); validate(p); run(p)
    shown = [show_expr_value(p, e) for e in p.show_exprs]
    assert shown[:3] == ['1', '5', '180']
    assert abs(float(shown[3]) - 3.141592653589793) < 1e-12
    assert shown[4:] == ['0', '1', '0']


def test_mod_number_validation():
    p = parse('let x = mod_number(7, 0)\nshow x\n'); validate(p)
    try:
        run(p)
    except RuntimeError as exc:
        assert 'non-zero divisor' in str(exc)
    else:
        raise AssertionError('expected mod_number validation to fail')
