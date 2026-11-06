"""Conformance tests for collection operations declared with `let`."""
from slang.core import parse, validate, run, show_expr_value


def _execute(source):
    program = parse(source)
    validate(program)
    run(program)
    return program


def test_let_where_declaration_is_accepted_and_executable():
    program = _execute('''
let values = [1, 2, 3, 4]
let large_values = values where item >= 3
show large_values
''')
    assert show_expr_value(program, program.show_exprs[0]) == '[3, 4]'


def test_let_map_declaration_is_accepted_and_executable():
    program = _execute('''
let values = [1, 2, 3]
let doubled = values map item * 2
show doubled
''')
    assert show_expr_value(program, program.show_exprs[0]) == '[2, 4, 6]'


def test_let_aggregate_declaration_is_accepted_and_executable():
    program = _execute('''
let values = [1, 2, 3]
let total = values sum
show total
''')
    assert show_expr_value(program, program.show_exprs[0]) == '6'


def test_let_reduce_declaration_is_accepted_and_executable():
    program = _execute('''
let values = [1, 2, 3]
let total = values reduce 0 with acc + item
show total
''')
    assert show_expr_value(program, program.show_exprs[0]) == '6'
