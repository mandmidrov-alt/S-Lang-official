from slang.ast import source_span_of
from slang.core import parse
from slang.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    SourceSpan,
    format_diagnostic,
)


def test_remaining_top_level_ast_nodes_have_source_spans():
    source = """module demo
record User:
    name: Text
function add(x: Number) -> Number:
    let y = x + 1
    return y
data people:
    alice age 20
users = people map age
show add(1)
"""
    program = parse(source)
    nodes = [
        program.ast.module,
        program.ast.records[0],
        program.ast.functions[0],
        program.ast.functions[0].body[0],
        program.ast.functions[0].body[1],
        program.ast.datasets[0],
        program.ast.maps[0],
        program.ast.shows[0],
    ]
    assert all(source_span_of(node) is not None for node in nodes)


def test_nested_expression_nodes_keep_precise_subexpression_ranges():
    source = 'let value = (1 + 2) * 3\n'
    program = parse(source)
    expr = program.ast.bindings[0].expr
    assert source_span_of(expr).start.line == 1
    assert source_span_of(expr).start.column == 13
    assert source_span_of(expr).end.column == 24
    assert source_span_of(expr.left).start.column == 13
    assert source_span_of(expr.left).end.column == 20
    assert source_span_of(expr.right).start.column == 23
    assert source_span_of(expr.right).end.column == 24


def test_row_binding_preserves_source_span():
    source = "people = people map age + 1\n"
    program = parse(source)
    expr = program.ast.maps[0].expr
    span = source_span_of(expr)
    assert span is not None
    assert span.start.line == 1
    assert span.start.column == 21
    assert span.end.column == 28


def test_explicit_multiline_span_formats_as_a_range():
    diagnostic = Diagnostic(
        DiagnosticSeverity.ERROR,
        "example",
        span=SourceSpan.range(2, 3, 4, 8),
    )
    rendered = format_diagnostic(diagnostic, "a\n  abc\nx\n123456789")
    assert "2:3-4:8" in rendered
    assert "through line 4:8" in rendered


def test_multiline_declaration_spans_cover_the_consumed_block():
    source = """function calc(x: Number) -> Number:
    if x > 0:
        return x + 1
    else:
        return x - 1
"""
    program = parse(source)
    fn = program.ast.functions[0]
    if_node = fn.body[0]
    assert source_span_of(fn).start.column == 1
    assert source_span_of(fn).end.line == 5
    assert source_span_of(if_node).start.line == 2
    assert source_span_of(if_node).end.line == 5


def test_nested_call_arguments_have_individual_ranges():
    source = 'show add(first + 1, second * "x")\n'
    program = parse(source)
    call = program.ast.shows[0].target
    first, second = call.args
    assert source_span_of(first).start.column < source_span_of(second).start.column
    assert source_span_of(first).end.column == source_span_of(first).start.column + len("first + 1")
    assert source_span_of(second).end.column == source_span_of(second).start.column + len('second * "x"')


def test_pipeline_stages_have_individual_source_ranges():
    source = "result = people |> where .age > 18 |> map .age + 1 |> sort by .age\n"
    program = parse(source)
    stages = [program.ast.filters[0], program.ast.maps[0], program.ast.sorts[0]]
    spans = [source_span_of(stage) for stage in stages]
    assert spans[0].start.column < spans[1].start.column < spans[2].start.column
    assert all(span.end.column > span.start.column for span in spans)
