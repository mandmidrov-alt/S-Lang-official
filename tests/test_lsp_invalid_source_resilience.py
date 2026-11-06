from slang.lsp_jsonrpc import LSPJsonRpcServer


def test_semantic_requests_on_invalid_source_return_protocol_fallback(monkeypatch):
    rpc = LSPJsonRpcServer()
    # The dispatch exception is the failure mode observed in VS Code when a
    # semantic feature cannot handle the current, incomplete source buffer.
    def broken_dispatch(method, params):
        raise ValueError("unknown syntax on line 3: sho value")
    monkeypatch.setattr(rpc, "_dispatch", broken_dispatch)

    cases = [
        ("textDocument/hover", None),
        ("textDocument/documentSymbol", []),
        ("textDocument/inlayHint", []),
        ("textDocument/semanticTokens/full", {"data": []}),
    ]
    for request_id, (method, expected) in enumerate(cases, 1):
        result = rpc.handle_message({
            "jsonrpc": "2.0", "id": request_id, "method": method, "params": {}
        })
        assert len(result) == 1
        assert result[0]["id"] == request_id
        assert result[0]["result"] == expected


def test_unrelated_internal_errors_remain_visible(monkeypatch):
    rpc = LSPJsonRpcServer()
    monkeypatch.setattr(rpc, "_dispatch", lambda method, params: (_ for _ in ()).throw(ValueError("boom")))
    result = rpc.handle_message({"jsonrpc": "2.0", "id": 7, "method": "workspace/symbol", "params": {}})
    assert result[0]["error"]["code"] == -32603


def test_missing_document_is_not_hidden_as_parse_error(monkeypatch):
    rpc = LSPJsonRpcServer()
    monkeypatch.setattr(rpc, "_dispatch", lambda method, params: (_ for _ in ()).throw(KeyError("document is not open")))
    result = rpc.handle_message({"jsonrpc": "2.0", "id": 8, "method": "textDocument/documentSymbol", "params": {}})
    assert result[0]["error"]["code"] == -32603
