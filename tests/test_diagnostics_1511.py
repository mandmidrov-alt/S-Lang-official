from slang.diagnostics import (
    Diagnostic, DiagnosticRelatedSpan, DiagnosticSeverity, SourceSpan,
    diagnostic_to_lsp, diagnostics_to_lsp, diagnostics_to_lsp_publish,
)


def test_lsp_maps_positions_and_severity():
    d = Diagnostic(DiagnosticSeverity.ERROR, "bad", code="E2000", phase="semantic", path="example.sl", span=SourceSpan.range(2, 14, 2, 28))
    out = diagnostic_to_lsp(d)
    assert out["severity"] == 1
    assert out["range"] == {"start": {"line": 1, "character": 13}, "end": {"line": 1, "character": 27}}
    assert out["code"] == "E2000"
    assert out["source"] == "slang"


def test_lsp_preserves_structured_metadata():
    d = Diagnostic(DiagnosticSeverity.WARNING, "bad", code="E2004", phase="semantic", category="type", tags=("semantic", "call"), hint="fix it", notes=("note",), data={"function": "join", "expected_type": "List<Text>", "actual_type": "Number"}, span=SourceSpan.line(1, 3))
    out = diagnostic_to_lsp(d)
    assert out["severity"] == 2
    assert out["data"]["slang_category"] == "type"
    assert out["data"]["slang_tags"] == ["semantic", "call"]
    assert out["data"]["diagnostic_data"]["function"] == "join"
    assert out["data"]["hint"] == "fix it"


def test_lsp_related_information_uses_source_uri():
    d = Diagnostic(DiagnosticSeverity.ERROR, "bad", code="E2000", path="example.sl", span=SourceSpan.range(1, 1, 1, 5), related=(DiagnosticRelatedSpan(SourceSpan.range(1, 7, 1, 10), "right operand"),))
    out = diagnostic_to_lsp(d)
    assert out["relatedInformation"][0]["location"]["uri"].startswith("file://")
    assert out["relatedInformation"][0]["location"]["range"]["start"]["character"] == 6
    assert out["relatedInformation"][0]["message"] == "right operand"


def test_publish_diagnostics_payload():
    d = Diagnostic(DiagnosticSeverity.INFO, "ok", code="E3000", path="example.sl", span=SourceSpan.line(3, 2))
    out = diagnostics_to_lsp_publish((d,), uri="file:///workspace/example.sl")
    assert out["uri"] == "file:///workspace/example.sl"
    assert len(out["diagnostics"]) == 1
    assert out["diagnostics"][0]["severity"] == 3


def test_lsp_sequence_preserves_order():
    ds = [Diagnostic(DiagnosticSeverity.ERROR, "a", code="E2000"), Diagnostic(DiagnosticSeverity.WARNING, "b", code="E2001")]
    assert [x["code"] for x in diagnostics_to_lsp(ds)] == ["E2000", "E2001"]
