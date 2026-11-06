from slang import LSPJsonRpcServer


def _initialize(rpc):
    return rpc.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "rootUri": "file:///tmp/project",
            "capabilities": {"workspace": {"configuration": True}},
        },
    })


def test_initialized_requests_workspace_configuration_when_client_supports_it():
    rpc = LSPJsonRpcServer()
    _initialize(rpc)
    messages = rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"})
    assert len(messages) == 1
    request = messages[0]
    assert request["method"] == "workspace/configuration"
    assert request["id"] == 1
    assert request["params"]["items"] == [{"scopeUri": "file:///tmp/project", "section": "slang"}]


def test_configuration_response_updates_server_settings_and_republishes():
    rpc = LSPJsonRpcServer()
    _initialize(rpc)
    rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"})
    rpc.handle_message({
        "jsonrpc": "2.0", "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///tmp/a.sl", "version": 1, "text": 'let x = 1 + "x"'}},
    })
    messages = rpc.handle_message({
        "jsonrpc": "2.0", "id": 1, "result": [{"diagnostics": {"enabled": False}}],
    })
    assert messages[0]["method"] == "textDocument/publishDiagnostics"
    assert messages[0]["params"]["diagnostics"] == []
    assert rpc.server.settings == {"slang": {"diagnostics": {"enabled": False}}} or rpc.server.settings == {"diagnostics": {"enabled": False}}


def test_configuration_error_response_is_consumed_without_notification():
    rpc = LSPJsonRpcServer()
    _initialize(rpc)
    rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"})
    assert rpc.handle_message({"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "not supported"}}) == ()
