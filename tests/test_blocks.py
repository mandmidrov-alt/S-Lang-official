import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value
from slang.ast import LetOp, ReturnOp


def test_function_supports_multiple_local_bindings():
    src = '''function adjusted(x: Number) -> Number:
    let doubled = x * 2
    let shifted = doubled + 3
    return shifted

show adjusted(5)
'''
    p = parse(src)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '13'
    body = p.ast.functions[0].body
    assert isinstance(body[0], LetOp)
    assert isinstance(body[1], LetOp)
    assert isinstance(body[2], ReturnOp)


def test_multiple_locals_work_in_filter_and_sort():
    src = '''function adjusted_score(score: Number, bonus: Number) -> Number:
    let boosted = score + bonus
    let normalized = boosted / 2
    return normalized

data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

selected = students where adjusted_score(score, 9) > 48
selected sort by adjusted_score(score, 9) desc
show selected
'''
    p = parse(src)
    validate(p)
    run(p)
    assert [r['name'] for r in p._collections['selected']] == ['Carol', 'Alice', 'Bob']


def test_local_variable_cannot_be_redeclared():
    src = '''function bad(x: Number) -> Number:
    let y = x + 1
    let y = y + 1
    return y
'''
    p = parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert "duplicate local variable 'y'" in str(e)
        return
    assert False
