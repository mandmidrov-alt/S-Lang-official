import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value


def test_user_function_works_in_filter_and_sort():
    src = '''function ratio(score: Number, age: Number) -> Number:\n    return score / age\n\ndata students:\n    Alice age 22 score 91\n    Bob age 17 score 88\n    Carol age 31 score 95\n\nselected = students where ratio(score, age) > 4\nselected sort by ratio(score, age) desc\nshow selected\n'''
    p=parse(src); validate(p); run(p)
    assert [r['name'] for r in p._collections['selected']] == ['Bob', 'Alice']
    assert show_expr_value(p, p.show_exprs[0]).startswith('[Bob')


def test_computed_property_uses_same_expression_system():
    src = '''property Circle.diameter -> m:\n    return self.radius * 2\n\ncircle disk:\n    center 0 m\n    radius 10 m\n\nshow disk.diameter\n'''
    p=parse(src); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '20 m'


def test_user_function_return_type_is_checked():
    src = '''function bad(x: Number) -> Boolean:\n    return x + 1\n\nshow bad(2)\n'''
    p=parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert "function 'bad' returns Number, declared Boolean" in str(e)
        return
    assert False


def test_computed_property_return_type_is_checked():
    src = '''property Circle.bad -> Number:\n    return self.radius * 2\n\ncircle disk:\n    radius 10 m\n\nshow disk.bad\n'''
    p=parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert "property 'Circle.bad' returns" in str(e)
        return
    assert False
