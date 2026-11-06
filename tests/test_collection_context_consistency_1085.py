"""Collection syntax conformance and context-boundary diagnostics for 1.0.85."""

import pytest

from slang.core import ParseError, parse, run, show_expr_value, validate


def _outputs(source):
    program = parse(source)
    validate(program)
    run(program)
    return [show_expr_value(program, expression) for expression in program.show_exprs]


def test_canonical_where_map_aggregate_chain_with_let():
    assert _outputs('''let scores = [92, 76, 88, 64, 95, 71]
let passing = scores where item >= 70
let doubled = passing map item * 2
let total = doubled sum
show total
''') == ["844"]


def test_canonical_let_sort_by():
    assert _outputs('''let values = [4, 1, 3, 2]
let sorted = values sort by item asc
show sorted
''') == ["[1, 2, 3, 4]"]


def test_canonical_let_pipeline():
    assert _outputs('''let values = [1, 2, 3, 4]
let result = values |> where item >= 2 |> map item * 3 |> sum
show result
''') == ["27"]


def test_lexical_variable_in_collection_predicate_is_not_a_row_field():
    assert _outputs('''let values = [1, 2, 3, 4]
let threshold = 2
let selected = values where item >= threshold
let total = selected sum
show total
''') == ["9"]


@pytest.mark.parametrize("statement", [
    "let filtered = values where item > 1",
    "let mapped = values map item * 2",
    "let total = values sum",
    "let sorted = values sort by item asc",
    "let total = values reduce 0 with acc + item",
    "let total = values |> map item * 2 |> sum",
])
def test_collection_transform_in_if_block_is_supported(statement):
    source = f'''let values = [1, 2, 3]
let enabled = true
if enabled:
    {statement}
else:
    show 0
'''
    program = parse(source)
    validate(program)


@pytest.mark.parametrize("statement", [
    "let filtered = values where item > 1",
    "let total = values |> sum",
])
def test_collection_transform_in_function_is_supported(statement):
    source = f'''function calculate(values: List<Number>) -> Number:
    {statement}
    return 0
let answer = calculate([1, 2, 3])
show answer
'''
    program = parse(source)
    validate(program)
