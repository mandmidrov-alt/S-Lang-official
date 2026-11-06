from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_initialize_advertises_execute_command():
    rpc = LSPJsonRpcServer()
    caps = init(rpc)[0]["result"]["capabilities"]
    assert caps["executeCommandProvider"]["commands"] == ["slang.applyWorkspaceEdit"]


def test_quickfix_is_executable_command_with_workspace_edit():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/fix.sl"
    open_doc(rpc, uri, "record User:\n  name: Text\n  age: Number\n\nlet user = User(\"A\", 20)\nlet x = user.nmae\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/codeAction", "params":{"textDocument":{"uri":uri},"range":{"start":{"line":5,"character":12},"end":{"line":5,"character":16}},"context":{}}})[0]
    assert response["result"]
    action = response["result"][0]
    assert "edit" not in action
    assert action["command"]["command"] == "slang.applyWorkspaceEdit"
    command_id = action["command"]["arguments"][0]
    executed = rpc.handle_message({"jsonrpc":"2.0", "id":3, "method":"workspace/executeCommand", "params":{"command":"slang.applyWorkspaceEdit", "arguments":[command_id]}})[0]
    assert executed["result"]["changes"][uri]


def test_unknown_execute_command_is_method_not_found():
    rpc = LSPJsonRpcServer(); init(rpc)
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"workspace/executeCommand", "params":{"command":"slang.nope","arguments":[]}})[0]
    assert response["error"]["code"] == -32601


def test_invalid_execute_command_arguments_are_invalid_params():
    rpc = LSPJsonRpcServer(); init(rpc)
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"workspace/executeCommand", "params":{"command":"slang.applyWorkspaceEdit","arguments":[]}})[0]
    assert response["error"]["code"] == -32602
