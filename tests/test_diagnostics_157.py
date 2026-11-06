from slang.diagnostics import diagnostic_definition, diagnostics_for_source


def test_diagnostic_definitions_have_machine_readable_categories_and_tags():
    assert diagnostic_definition("E2002").category == "name"
    assert "function" in diagnostic_definition("E2002").tags
    assert diagnostic_definition("E2003").category == "arity"
    assert "type" in diagnostic_definition("E2004").tags
    assert diagnostic_definition("E2005").category == "field"
    assert diagnostic_definition("E2006").category == "condition"


def test_json_diagnostics_expose_category_and_tags():
    bag = diagnostics_for_source('let x = missing(1)\n', path='example.sl')
    payload = bag.to_dict()[0]
    assert payload["code"] == "E2002"
    assert payload["category"] == "name"
    assert "function" in payload["tags"]


def test_diagnostic_explicit_data_is_machine_readable():
    from slang.diagnostics import Diagnostic, DiagnosticSeverity
    d = Diagnostic(
        DiagnosticSeverity.ERROR, "bad operator", code="E2000",
        data={"operator": "+", "left_type": "Number", "right_type": "Text"},
    )
    payload = d.to_dict()
    assert payload["data"]["operator"] == "+"
    assert payload["data"]["left_type"] == "Number"
