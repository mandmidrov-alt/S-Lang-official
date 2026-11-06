from slang.core import parse, validate, run
from slang.ast import Logical


def test_compound_boolean_predicate():
    src = '''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\n    Carol age 31 score 95\n    Dave age 25 score 72\n\nselected = people where age >= 18 and score >= 90\nshow selected\n'''
    p = parse(src)
    assert isinstance(p.ast.filters[0].predicate.expr, Logical)
    validate(p); run(p)
    assert [r['name'] for r in p._collections['selected']] == ['Alice', 'Carol']


def test_boolean_precedence_and_parentheses():
    src = '''data people:\n    A age 10 score 100\n    B age 20 score 80\n    C age 30 score 95\n    D age 40 score 70\n\nselected = people where age >= 30 or score >= 100 and age < 20\nshow selected\n'''
    p = parse(src); validate(p); run(p)
    assert [r['name'] for r in p._collections['selected']] == ['A', 'C', 'D']


def test_not_boolean_expression():
    src = '''data people:\n    A age 10 score 100\n    B age 20 score 80\n    C age 30 score 95\n\nselected = people where not (age < 20)\nshow selected\n'''
    p = parse(src); validate(p); run(p)
    assert [r['name'] for r in p._collections['selected']] == ['B', 'C']


def test_non_boolean_logical_operand_rejected():
    src = '''data people:\n    A age 10 score 100\n\nselected = people where age and score > 10\nshow selected\n'''
    p = parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert 'logical operand must be Boolean' in str(e)
        return
    assert False
