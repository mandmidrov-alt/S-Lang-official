from slang.core import parse_expr
from slang.ast import Call, Conditional, Logical


def test_constructor_arguments_accept_full_expressions():
    expr = parse_expr('Final(if row.active then row.name else "inactive", row.active and row.score > 80, not row.active)')
    assert isinstance(expr, Call)
    assert len(expr.args) == 3
    assert isinstance(expr.args[0], Conditional)
    assert isinstance(expr.args[1], Logical)
    assert isinstance(expr.args[2], Logical)
