import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value, ParseError


def test_if_else_returns_from_function():
    src = '''function classify(x: Number) -> Number:
    if x >= 10:
        return 100
    else:
        return 0

show classify(12)
'''
    p = parse(src); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '100'


def test_if_branch_can_continue_with_local_bindings():
    src = '''function adjust(x: Number) -> Number:
    let base = x * 2
    if x >= 10:
        let extra = 5
        return base + extra
    return base

show adjust(12)
show adjust(3)
'''
    p = parse(src); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '29'
    assert show_expr_value(p, p.show_exprs[1]) == '6'


def test_if_condition_must_be_boolean():
    src = '''function bad(x: Number) -> Number:
    if x:
        return 1
    return 0
'''
    p = parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert 'if condition must be Boolean' in str(e)
        return
    assert False


def test_if_branches_must_have_compatible_return_types():
    src = '''function bad(x: Number) -> Number:
    if x >= 0:
        return 1
    else:
        return 2 kg
'''
    p = parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert 'if branches return incompatible types' in str(e)
        return
    assert False
