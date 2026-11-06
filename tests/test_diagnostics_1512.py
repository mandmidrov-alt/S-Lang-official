from slang.diagnostics import (
    Diagnostic, DiagnosticSeverity, SourcePosition, SourceSpan,
    diagnostics_to_lsp_publish, diagnostics_to_lsp_publish_documents,
)


def diag(path, line=1):
    return Diagnostic(
        DiagnosticSeverity.ERROR, "bad", code="E2000", path=path,
        span=SourceSpan(SourcePosition(line, 1), SourcePosition(line, 4)),
    )


def test_publish_supports_optional_document_version():
    payload = diagnostics_to_lsp_publish([diag("/tmp/a.sl")], uri="file:///tmp/a.sl", version=7)
    assert payload["uri"] == "file:///tmp/a.sl"
    assert payload["version"] == 7
    assert len(payload["diagnostics"]) == 1


def test_publish_omits_version_when_not_supplied():
    payload = diagnostics_to_lsp_publish([], uri="file:///tmp/a.sl")
    assert payload == {"uri": "file:///tmp/a.sl", "diagnostics": []}


def test_documents_group_by_uri_and_sort_stably():
    payloads = diagnostics_to_lsp_publish_documents([
        diag("/tmp/b.sl", 2), diag("/tmp/a.sl", 3), diag("/tmp/b.sl", 5)
    ])
    assert [item["uri"] for item in payloads] == ["file:///tmp/a.sl", "file:///tmp/b.sl"]
    assert len(payloads[1]["diagnostics"]) == 2
    assert payloads[1]["diagnostics"][0]["range"]["start"]["line"] == 1


def test_documents_can_clear_clean_uris():
    payloads = diagnostics_to_lsp_publish_documents(
        [diag("/tmp/a.sl")], uris=["file:///tmp/a.sl", "file:///tmp/clean.sl"]
    )
    clean = next(item for item in payloads if item["uri"] == "file:///tmp/clean.sl")
    assert clean["diagnostics"] == []


def test_documents_apply_versions_by_uri():
    payloads = diagnostics_to_lsp_publish_documents(
        [diag("/tmp/a.sl")], versions={"file:///tmp/a.sl": 12}
    )
    assert payloads[0]["version"] == 12
