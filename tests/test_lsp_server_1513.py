from slang import LSPServer


def test_initialize_advertises_document_sync_and_push_diagnostics():
    server = LSPServer()
    result = server.initialize()
    assert result["serverInfo"]["version"] == "1.0"
    assert result["capabilities"]["textDocumentSync"]["openClose"] is True
    assert "diagnosticProvider" not in result["capabilities"]


def test_open_publishes_diagnostics_with_version():
    server = LSPServer()
    server.initialize()
    uri = "file:///tmp/example.sl"
    payload = server.did_open(uri, 'let x = 1 + "text"\n', version=7)
    assert payload["uri"] == uri
    assert payload["version"] == 7
    assert payload["diagnostics"][0]["code"] == "E2000"


def test_change_replaces_document_and_clears_fixed_diagnostics():
    server = LSPServer()
    server.initialize()
    uri = "file:///tmp/example.sl"
    server.did_open(uri, 'let x = 1 + "text"\n', version=1)
    payload = server.did_change(uri, "let x = 1 + 2\n", version=2)
    assert payload["version"] == 2
    assert payload["diagnostics"] == []
    assert server.documents[0].text == "let x = 1 + 2\n"


def test_close_clears_diagnostics():
    server = LSPServer()
    server.initialize()
    uri = "file:///tmp/example.sl"
    server.did_open(uri, "let x = 1\n", version=1)
    payload = server.did_close(uri)
    assert payload == {"uri": uri, "diagnostics": []}
    assert server.documents == ()


def test_change_requires_open_document():
    server = LSPServer()
    try:
        server.did_change("file:///tmp/missing.sl", "let x = 1")
    except KeyError as exc:
        assert "not open" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_diagnostics_returns_native_slang_diagnostics():
    server = LSPServer()
    uri = "file:///tmp/example.sl"
    server.did_open(uri, 'let x = 1 + "text"\n')
    diagnostics = server.diagnostics(uri)
    assert diagnostics[0].code == "E2000"
    assert diagnostics[0].path == uri
