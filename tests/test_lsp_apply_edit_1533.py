from slang import LSPJsonRpcServer


def init(rpc, capabilities=None):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{"capabilities": capabilities or {}}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_initialize_advertises_execute_command_without_requiring_apply_edit():
    rpc = LSPJsonRpcServer()
    caps = init(rpc)[0]["result"]["capabilities"]
    assert caps["executeCommandProvider"]["commands"] == ["slang.applyWorkspaceEdit"]


def test_execute_command_emits_workspace_apply_edit_request_when_client_supports_it():
    caps = {"workspace": {"applyEdit": True}}
    rpc = LSPJsonRpcServer(); init(rpc, caps)
    uri = "file:///tmp/fix.sl"
    open_doc(rpc, uri, "record User:\n  name: Text\n  age: Number\n\nlet user = User(\"A\", 20)\nlet x = user.nmae\n")
    action = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/codeAction", "params":{"textDocument":{"uri":uri},"range":{"start":{"line":5,"character":12},"end":{"line":5,"character":16}},"context":{}}})[0]["result"][0]
    command_id = action["command"]["arguments"][0]
    messages = rpc.handle_message({"jsonrpc":"2.0", "id":3, "method":"workspace/executeCommand", "params":{"command":"slang.applyWorkspaceEdit","arguments":[command_id]}})
    assert messages[0]["id"] == 3
    assert messages[0]["result"]["changes"][uri]
    assert messages[1]["method"] == "workspace/applyEdit"
    assert messages[1]["params"]["edit"] == messages[0]["result"]
    assert isinstance(messages[1]["id"], int)


def test_workspace_apply_edit_response_is_consumed():
    rpc = LSPJsonRpcServer(); init(rpc, {"workspace": {"applyEdit": True}})
    uri = "file:///tmp/fix.sl"
    open_doc(rpc, uri, "let name = 1\nlet value = name\n")
    # Register an edit through a code action so executeCommand has a server request to emit.
    rpc.server._command_edits["test.edit"] = {"changes": {uri: [{"range": {"start": {"line": 0, "character": 4}, "end": {"line": 0, "character": 8}}, "newText": "x"}]}}
    messages = rpc.handle_message({"jsonrpc":"2.0", "id":4, "method":"workspace/executeCommand", "params":{"command":"slang.applyWorkspaceEdit","arguments":["test.edit"]}})
    server_request = messages[1]
    response = rpc.handle_message({"jsonrpc":"2.0", "id":server_request["id"], "result":{"applied":True}})
    assert response == ()


def test_no_apply_edit_request_without_client_capability():
    rpc = LSPJsonRpcServer(); init(rpc)
    rpc.server._command_edits["test.edit"] = {"changes": {"file:///tmp/x.sl": []}}
    messages = rpc.handle_message({"jsonrpc":"2.0", "id":4, "method":"workspace/executeCommand", "params":{"command":"slang.applyWorkspaceEdit","arguments":["test.edit"]}})
    assert len(messages) == 1
