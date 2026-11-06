from slang.diagnostics import (
    DIAGNOSTIC_PROTOCOL_NAME, DIAGNOSTIC_PROTOCOL_VERSION,
    Diagnostic, DiagnosticRelatedSpan, DiagnosticSeverity, SourceSpan,
    deserialize_diagnostic, deserialize_diagnostics, diagnostics_for_source,
    serialize_diagnostic, serialize_diagnostics,
)

def test_single_diagnostic_protocol_round_trip_is_canonical():
    diagnostic = Diagnostic(DiagnosticSeverity.ERROR, "cannot add Number and Text", code="E2000", phase="semantic", span=SourceSpan.range(2,14,2,28), path="example.sl", related=(DiagnosticRelatedSpan(SourceSpan.range(2,14,2,19), "left operand"),), notes=("left operand has type Number",), hint="use compatible operand types", category="type", tags=("semantic","type"), data={"operator":"+","left_type":"Number","right_type":"Text"})
    encoded = serialize_diagnostic(diagnostic)
    restored = deserialize_diagnostic(encoded)
    assert restored == diagnostic
    assert encoded == serialize_diagnostic(restored)
    assert f'"name":"{DIAGNOSTIC_PROTOCOL_NAME}"' in encoded
    assert f'"version":{DIAGNOSTIC_PROTOCOL_VERSION}' in encoded

def test_diagnostic_sequence_preserves_order_and_empty_payload():
    diagnostics = diagnostics_for_source('let x = missing(1)\n', path='example.sl').diagnostics
    restored = deserialize_diagnostics(serialize_diagnostics(diagnostics))
    assert [item.to_dict() for item in restored] == [item.to_dict() for item in diagnostics]
    assert deserialize_diagnostics(serialize_diagnostics(())) == ()

def test_protocol_rejects_wrong_name_and_version():
    for payload in ('{"protocol":{"name":"other","version":1},"diagnostic":{}}', '{"protocol":{"name":"slang-diagnostics","version":99},"diagnostic":{}}'):
        try: deserialize_diagnostic(payload)
        except ValueError: pass
        else: raise AssertionError("invalid protocol payload was accepted")

def test_protocol_rejects_invalid_structured_data():
    payload = {"protocol":{"name":"slang-diagnostics","version":1},"diagnostic":{"severity":"error","code":"E2003","phase":"semantic","message":"bad","data":{"function":"len","expected_arity":"1","actual_arity":2}}}
    try: deserialize_diagnostic(payload)
    except ValueError as exc: assert "invalid diagnostic data" in str(exc)
    else: raise AssertionError("invalid diagnostic data was accepted")
