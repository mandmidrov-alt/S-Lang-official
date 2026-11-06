from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import BOOLEAN, NUMBER


def test_numeric_predicate_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('is_finite_number(12)'), env) == BOOLEAN
    assert infer(parse_expr('is_nan_number(12)'), env) == BOOLEAN
    assert infer(parse_expr('is_integer_number(12)'), env) == BOOLEAN
    assert infer(parse_expr('reciprocal_number(4)'), env) == NUMBER


def test_numeric_predicates_and_reciprocal():
    source = '''let a = is_finite_number(12)\nlet b = is_nan_number(12)\nlet c = is_integer_number(12)\nlet d = is_integer_number(12.5)\nlet e = reciprocal_number(4)\nshow a\nshow b\nshow c\nshow d\nshow e\n'''
    p = parse(source); validate(p); run(p)
    assert [show_expr_value(p, e) for e in p.show_exprs] == ['True', 'False', 'True', 'False', '0.25']


def test_reciprocal_zero_fails():
    p = parse('let x = reciprocal_number(0)\nshow x\n'); validate(p)
    try:
        run(p)
    except RuntimeError as exc:
        assert 'non-zero' in str(exc)
    else:
        raise AssertionError('expected reciprocal_number(0) to fail')
