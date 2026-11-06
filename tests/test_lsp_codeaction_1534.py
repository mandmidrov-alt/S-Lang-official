from slang import LSPServer, LSPJsonRpcServer


def test_interfile_selective_export_quickfix_has_composite_workspace_edit():
    server = LSPServer()
    src = "file:///tmp/provider_1534.sl"
    consumer = "file:///tmp/consumer_1534.sl"
    server.did_open(src, 'export greet, other\n\nfunction greet(name: Text) -> Text:\n  return name\n\nfunction other(name: Text) -> Text:\n  return name\n')
    server.did_open(consumer, 'import "provider_1534.sl" { greet }\n\nlet x = other("A")\n')
    actions = server.code_actions(consumer, diagnostics=[{
        "code": "E2001", "message": "unknown name 'other'",
        "data": {"name": "other"},
        "range": {"start": {"line": 2, "character": 8}, "end": {"line": 2, "character": 13}},
    }])
    assert actions
    action = actions[-1]
    assert action['command']['command'] == 'slang.applyWorkspaceEdit'
    edit = server.execute_command(action['command']['command'], action['command']['arguments'])
    assert set(edit['changes']) == {consumer, src}
    assert edit['changes'][consumer]
    assert edit['changes'][src]


def test_interfile_fix_is_not_offered_without_explicit_export_list():
    server = LSPServer()
    src = "file:///tmp/provider_1534b.sl"
    consumer = "file:///tmp/consumer_1534b.sl"
    server.did_open(src, 'function greet(name: Text) -> Text:\n  return name\n')
    server.did_open(consumer, 'import "provider_1534b.sl" { greet }\n\nlet x = other("A")\n')
    diagnostics = [{"code": "E2001", "message": "unknown name 'other'", "data": {"name": "other"}, "range": {"start": {"line": 2, "character": 8}, "end": {"line": 2, "character": 13}}}]
    assert not [a for a in server.code_actions(consumer, diagnostics=diagnostics) if 'Export' in a.get('title', '')]


def test_jsonrpc_executes_composite_workspace_edit_and_requests_apply_edit():
    rpc = LSPJsonRpcServer()
    init = rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{"capabilities":{"workspace":{"applyEdit":True}}}})
    assert init[0]["result"]["capabilities"]["executeCommandProvider"]["commands"]
    src = "file:///tmp/provider_1534c.sl"; consumer = "file:///tmp/consumer_1534c.sl"
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":src,"version":1,"text":'export greet, other\n\nfunction greet(name: Text) -> Text:\n  return name\n\nfunction other(name: Text) -> Text:\n  return name\n'}}})
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":consumer,"version":1,"text":'import "provider_1534c.sl" { greet }\n\nlet x = other("A")\n'}}})
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/codeAction", "params":{"textDocument":{"uri":consumer},"range":{"start":{"line":2,"character":0},"end":{"line":2,"character":13}},"context":{"diagnostics":[{"code":"E2001","message":"unknown name 'other'","data":{"name":"other"},"range":{"start":{"line":2,"character":8},"end":{"line":2,"character":13}}}]}}})
    action=response[0]["result"][-1]
    command=action["command"]
    out=rpc.handle_message({"jsonrpc":"2.0","id":3,"method":"workspace/executeCommand","params":{"command":command["command"],"arguments":command["arguments"]}})
    assert out[0]["result"]["changes"][src]
    assert any(item.get("method")=="workspace/applyEdit" for item in out[1:])
