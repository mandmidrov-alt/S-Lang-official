from pathlib import Path
import sys
sys.path.insert(0, '.')
from slang.core import parse, validate
from slang.ast import Compare, Field, Literal, FilterOp, SortOp

def test_parser_builds_generic_semantic_ast():
    p=parse(Path('examples/data_generic.sl').read_text())
    validate(p)
    assert isinstance(p.ast.filters[0], FilterOp)
    expr=p.ast.filters[0].predicate.expr
    assert isinstance(expr, Compare)
    assert isinstance(expr.left, Field)
    assert expr.left.name == 'age'
    assert isinstance(expr.right, Literal)
    assert expr.right.value == 18
    assert isinstance(p.ast.sorts[0], SortOp)
    assert isinstance(p.ast.sorts[0].spec.expr, __import__('slang.ast', fromlist=['Binary']).Binary)
