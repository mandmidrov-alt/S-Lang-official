from slang.diagnostics import diagnostic_definition, diagnostic_definitions, diagnostics_for_source


def test_diagnostic_definitions_are_stable():
    assert diagnostic_definition("E2002").phase == "semantic"
    assert diagnostic_definition("E2003").hint
    assert {d.code for d in diagnostic_definitions()} >= {"E1000", "E2000", "E2002", "E2003", "E2004", "E2005", "E2006"}


def test_unknown_function_has_stable_code_and_span():
    bag = diagnostics_for_source('let x = missing(1)\n', path='example.sl')
    d = bag.diagnostics[0]
    assert d.code == "E2002"
    assert d.phase == "semantic"
    assert d.span.start.column == 9
    assert d.span.end.column == 19


def test_argument_count_has_stable_code():
    bag = diagnostics_for_source('let x = len(1, 2)\n', path='example.sl')
    assert bag.diagnostics[0].code == "E2003"


def test_argument_type_has_stable_code():
    bag = diagnostics_for_source('let x = len("text")\n', path='example.sl')
    # len accepts Any, so this is valid; use join instead.
    bag = diagnostics_for_source('let x = join(1, "-")\n', path='example.sl')
    assert bag.diagnostics[0].code == "E2004"
