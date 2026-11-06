from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER


def test_math_1117_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('min_of_numbers(4, 7)'), env) == NUMBER
    assert infer(parse_expr('max_of_numbers(4, 7)'), env) == NUMBER
    assert infer(parse_expr('lerp_number(0, 10, 0.25)'), env) == NUMBER
    assert infer(parse_expr('log_number(8, 2)'), env) == NUMBER
    assert infer(parse_expr('exp_number(0)'), env) == NUMBER


def test_math_1117_runtime():
    source = '''let a = min_of_numbers(4, 7)
let b = max_of_numbers(4, 7)
let c = lerp_number(0, 10, 0.25)
let d = log_number(8, 2)
let e = exp_number(0)
show a
show b
show c
show d
show e
'''
    p = parse(source); validate(p); run(p)
    assert [show_expr_value(p, e) for e in p.show_exprs] == ['4', '7', '2.5', '3', '1']


def test_log_number_validation():
    for source, expected in [
        ('let x = log_number(0, 10)\nshow x\n', 'positive value'),
        ('let x = log_number(10, 1)\nshow x\n', 'positive base different from 1'),
    ]:
        p = parse(source); validate(p)
        try:
            run(p)
        except RuntimeError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError('expected log_number validation to fail')
