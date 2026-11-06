from slang.ast import Name, Literal, source_span_of
from slang.core import parse, validate
from slang.diagnostics import diagnostics_for_source


def test_expression_source_span_is_preserved():
    source = 'let value = 42\n'
    program = parse(source)
    expr = program.ast.bindings[0].expr
    span = source_span_of(expr)
    assert span is not None
    assert span.start.line == 1
    assert span.start.column == 13


def test_semantic_diagnostic_points_to_expression_line():
    source = 'let value = 1\nlet broken = unknown(1)\n'
    diagnostics = diagnostics_for_source(source, path='example.sl')
    assert diagnostics.has_errors
    diagnostic = diagnostics.diagnostics[0]
    assert diagnostic.code == 'E2002'
    assert diagnostic.phase == 'semantic'
    assert diagnostic.span is not None
    assert diagnostic.span.start.line == 2
    assert diagnostic.span.start.column >= 1


def test_multiline_semantic_error_keeps_exact_statement_line():
    source = 'let first = 1\nlet second = first + "text"\n'
    diagnostics = diagnostics_for_source(source)
    assert diagnostics.has_errors
    diagnostic = diagnostics.diagnostics[0]
    assert diagnostic.span is not None
    assert diagnostic.span.start.line == 2
