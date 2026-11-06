from slang.lsp_server import LSPServer
from slang.lsp_jsonrpc import LSPJsonRpcServer


def _initialize(rpc):
    return rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"workspaceFolders": []}})


def test_workspace_configuration_is_stored_and_affects_diagnostics():
    server = LSPServer()
    server.initialize()
    server.did_open("file:///tmp/a.sl", 'let x = 1 + "x"')
    assert server.diagnostics("file:///tmp/a.sl")
    publications = server.did_change_configuration({"slang": {"diagnostics": {"enabled": False}}})
    assert publications[0]["diagnostics"] == []
    assert server.diagnostics("file:///tmp/a.sl") == ()
    assert server.settings["slang"]["diagnostics"]["enabled"] is False


def test_diagnostic_max_problems_is_deterministic():
    server = LSPServer()
    server.initialize()
    server.did_open("file:///tmp/a.sl", 'let a = 1 + "x"')
    assert server.diagnostics("file:///tmp/a.sl")
    server.did_change_configuration({"slang": {"diagnostics": {"maxProblems": 0}}})
    assert server.diagnostics("file:///tmp/a.sl") == ()


def test_jsonrpc_configuration_notification_republishes_diagnostics():
    rpc = LSPJsonRpcServer()
    _initialize(rpc)
    rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"})
    opened = rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": "file:///tmp/a.sl", "text": 'let x = 1 + "x"', "version": 1}}})
    assert opened and opened[0]["method"] == "textDocument/publishDiagnostics"
    result = rpc.handle_message({"jsonrpc": "2.0", "method": "workspace/didChangeConfiguration", "params": {"settings": {"slang": {"diagnostics": {"enabled": False}}}}})
    assert result[0]["params"]["diagnostics"] == []


def test_workspace_folders_change_is_applied():
    server = LSPServer()
    server.initialize(workspace_folders=[{"uri": "file:///a", "name": "a"}])
    server.did_change_workspace_folders({"added": [{"uri": "file:///b", "name": "b"}], "removed": [{"uri": "file:///a", "name": "a"}]})
    assert [item["uri"] for item in server.workspace_folders] == ["file:///b"]


def test_initialize_advertises_workspace_configuration_capabilities():
    server = LSPServer()
    result = server.initialize()
    assert result["capabilities"]["workspace"]["workspaceFolders"]["supported"] is True
    assert result["capabilities"]["configuration"] is True


def test_jsonrpc_workspace_folders_notification():
    rpc = LSPJsonRpcServer()
    _initialize(rpc)
    rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"})
    result = rpc.handle_message({"jsonrpc": "2.0", "method": "workspace/didChangeWorkspaceFolders", "params": {"event": {"added": [{"uri": "file:///b", "name": "b"}], "removed": []}}})
    assert result == ()
    assert rpc.server.workspace_folders == ({"uri": "file:///b", "name": "b"},)
