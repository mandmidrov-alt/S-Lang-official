from pathlib import Path
import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value
from slang.ast import Compare, Binary, Field, Name


def test_where_uses_generic_expression_ast():
    p = parse(Path('examples/data_generic.sl').read_text())
    assert isinstance(p.ast.filters[0].predicate.expr, Compare)
    assert isinstance(p.ast.sorts[0].spec.expr, Binary)
    validate(p)
    run(p)
    assert [r['name'] for r in p._collections['adults']] == ['Alice', 'Carol', 'Eve']
    assert [r['name'] for r in p._collections['ranked']] == ['Alice', 'Eve', 'Carol']


def test_complex_filter_expression():
    src = '''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\n    Carol age 31 score 95\n\nselected = people where score / age > 4\nshow selected\n'''
    p = parse(src); validate(p); run(p)
    assert [r['name'] for r in p._collections['selected']] == ['Alice', 'Bob']


def test_unknown_sort_field_is_rejected():
    src = '''data people:\n    Alice age 22\n\nselected = people where age >= 18\nselected sort by salary\nshow selected\n'''
    p = parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert 'unknown field' in str(e)
        return
    assert False
