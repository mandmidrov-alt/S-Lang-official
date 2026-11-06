from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER


def test_math_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('clamp_number(12, 0, 10)'), env) == NUMBER
    assert infer(parse_expr('sign_number(0 - 4)'), env) == NUMBER
    assert infer(parse_expr('pow_number(2, 3)'), env) == NUMBER


def test_math_runtime():
    source = '''let a = clamp_number(12, 0, 10)
let b = clamp_number(0 - 2, 0, 10)
let c = sign_number(0 - 7)
let d = sign_number(0)
let e = sign_number(8)
let f = pow_number(2, 5)
show a
show b
show c
show d
show e
show f
'''
    p = parse(source); validate(p); run(p)
    assert [show_expr_value(p, e) for e in p.show_exprs] == ['10', '0', '-1', '0', '1', '32']


def test_clamp_invalid_bounds():
    source = 'let x = clamp_number(1, 10, 0)\nshow x\n'
    p = parse(source); validate(p)
    try:
        run(p)
    except RuntimeError as exc:
        assert 'minimum <= maximum' in str(exc)
    else:
        raise AssertionError('expected invalid clamp bounds to fail')
