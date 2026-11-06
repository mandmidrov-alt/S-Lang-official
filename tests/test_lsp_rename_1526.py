from slang.lsp_server import LSPServer
from slang.lsp_jsonrpc import LSPJsonRpcServer


def uri(name):
    return "file:///tmp/" + name


def test_document_highlight_and_prepare_rename():
    server = LSPServer()
    server.initialize()
    u = uri("main.sl")
    server.did_open(u, "let value = 1\nlet result = value + value\n")
    highlights = server.document_highlight(u, 1, 13)
    assert len(highlights) == 3
    prepared = server.prepare_rename(u, 1, 13)
    assert prepared["placeholder"] == "value"
    assert prepared["range"]["start"] == {"line": 0, "character": 4}


def test_workspace_rename_is_deterministic():
    server = LSPServer()
    server.initialize()
    a, b = uri("a.sl"), uri("b.sl")
    server.did_open(a, "import b\nlet value = 1\nlet x = value\n")
    server.did_open(b, "import a\nlet y = value + 1\n")
    edit = server.rename(a, 2, 8, "total")
    assert list(edit["changes"]) == [a, b]
    assert len(edit["changes"][a]) == 2
    assert len(edit["changes"][b]) == 1
    assert all(item["newText"] == "total" for items in edit["changes"].values() for item in items)


def test_jsonrpc_rename_methods_and_capabilities():
    rpc = LSPJsonRpcServer(LSPServer())
    init = rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    caps = init[0]["result"]["capabilities"]
    assert caps["documentHighlightProvider"] is True
    assert caps["renameProvider"] == {"prepareProvider": True}
    rpc.handle_message({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri("a.sl"), "version": 1, "text": "let value = 1\nlet out = value\n"}}})
    prepared = rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "textDocument/prepareRename", "params": {"textDocument": {"uri": uri("a.sl")}, "position": {"line": 1, "character": 13}}})
    assert prepared[0]["result"]["placeholder"] == "value"
    renamed = rpc.handle_message({"jsonrpc": "2.0", "id": 3, "method": "textDocument/rename", "params": {"textDocument": {"uri": uri("a.sl")}, "position": {"line": 1, "character": 13}, "newName": "total"}})
    assert renamed[0]["result"]["changes"][uri("a.sl")][0]["newText"] == "total"


def test_invalid_rename_returns_no_edit():
    server = LSPServer()
    server.initialize()
    u = uri("main.sl")
    server.did_open(u, "let value = 1\nvalue\n")
    assert server.rename(u, 1, 2, "") is None
    assert server.rename(u, 1, 2, "123bad") is None
