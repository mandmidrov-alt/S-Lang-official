from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})


def open_doc(rpc, uri, text, version=1):
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "version": version, "text": text}}})


def test_initialize_advertises_range_and_full_semantic_tokens(tmp_path):
    rpc = LSPJsonRpcServer()
    provider = init(rpc)[0]["result"]["capabilities"]["semanticTokensProvider"]
    assert provider["range"] is True
    assert provider["full"] is True


def test_semantic_tokens_range_returns_only_requested_lines(tmp_path):
    uri = (tmp_path / "main.sl").as_uri()
    rpc = LSPJsonRpcServer(); init(rpc); open_doc(rpc, uri, "let first = 1\nlet second = 2\n")
    result = rpc.handle_message({"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/range","params":{"textDocument":{"uri":uri},"range":{"start":{"line":1,"character":0},"end":{"line":1,"character":99}}}})[0]["result"]
    assert result["data"]
    assert result["data"][0] == 1


def test_semantic_tokens_delta_returns_edit_after_change(tmp_path):
    uri = (tmp_path / "main.sl").as_uri()
    rpc = LSPJsonRpcServer(); init(rpc); open_doc(rpc, uri, "let value = 1\n")
    first = rpc.handle_message({"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/full","params":{"textDocument":{"uri":uri}}})[0]["result"]
    rpc.handle_message({"jsonrpc":"2.0","method":"textDocument/didChange","params":{"textDocument":{"uri":uri,"version":2},"contentChanges":[{"text":"let changed = 2\n"}]}})
    delta = rpc.handle_message({"jsonrpc":"2.0","id":3,"method":"textDocument/semanticTokens/full","params":{"textDocument":{"uri":uri},"previousResultId":first["resultId"]}})[0]["result"]
    assert "edits" in delta
    assert delta["resultId"] != first["resultId"]


def test_unknown_previous_result_returns_full_result(tmp_path):
    uri = (tmp_path / "main.sl").as_uri()
    rpc = LSPJsonRpcServer(); init(rpc); open_doc(rpc, uri, "let value = 1\n")
    result = rpc.handle_message({"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/full","params":{"textDocument":{"uri":uri},"previousResultId":"unknown"}})[0]["result"]
    assert "data" in result
    assert "edits" not in result
