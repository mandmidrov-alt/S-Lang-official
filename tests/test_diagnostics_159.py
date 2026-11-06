from slang.diagnostics import (
    Diagnostic, DiagnosticSeverity, diagnostic_schema, diagnostic_schemas,
    diagnostics_for_source, validate_diagnostic_data,
)


def test_diagnostic_schemas_are_typed_and_stable():
    schema = diagnostic_schema("E2003")
    assert schema is not None
    assert schema.required_fields == ("function", "expected_arity", "actual_arity")
    assert schema.field("expected_arity").value_type == "integer"
    assert diagnostic_schema("E2004").field("expected_type").value_type == "type"


def test_schema_validation_accepts_semantic_payloads():
    assert validate_diagnostic_data("E2003", {
        "function": "len", "expected_arity": 1, "actual_arity": 2,
    }) == ()
    assert validate_diagnostic_data("E2006", {
        "expected_type": "Boolean", "actual_type": "Number", "operand": "left",
    }) == ()


def test_schema_validation_reports_missing_wrong_and_unknown_fields():
    errors = validate_diagnostic_data("E2003", {"function": "len", "actual_arity": "2", "extra": True})
    assert "missing required diagnostic field 'expected_arity'" in errors
    assert "diagnostic field 'actual_arity' must be integer" in errors
    assert "unknown diagnostic field 'extra' for E2003" in errors


def test_enum_validation_is_machine_readable():
    errors = validate_diagnostic_data("E2006", {
        "expected_type": "Boolean", "actual_type": "Number", "operand": "middle",
    })
    assert "diagnostic field 'operand' must be one of ('left', 'right')" in errors


def test_json_exposes_schema_and_data_together():
    bag = diagnostics_for_source('let x = missing(1)\n', path='example.sl')
    payload = bag.to_dict()[0]
    assert payload["code"] == "E2002"
    assert payload["schema"]["fields"][0]["name"] == "function"
    assert payload["schema"]["fields"][0]["required"] is True
    assert payload["data"]["function"] == "missing"


def test_all_defined_schemas_are_queryable():
    schemas = diagnostic_schemas()
    assert set(schemas) >= {"E2000", "E2001", "E2002", "E2003", "E2004", "E2005", "E2006"}
