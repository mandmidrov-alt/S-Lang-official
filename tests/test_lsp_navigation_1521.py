from slang import LSPJsonRpcServer, LSPServer


def init(rpc):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_initialize_advertises_navigation_capabilities():
    rpc = LSPJsonRpcServer()
    result = init(rpc)[0]["result"]["capabilities"]
    assert result["documentSymbolProvider"] is True
    assert result["workspaceSymbolProvider"] is True
    assert result["definitionProvider"] is True


def test_document_symbols_returns_top_level_symbols_with_ranges():
    rpc = LSPJsonRpcServer()
    init(rpc)
    uri = "file:///tmp/nav.sl"
    open_doc(rpc, uri, "function add(a: Number) -> Number:\n  return a + 1\n\nrecord User:\n  name: Text\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/documentSymbol", "params":{"textDocument":{"uri":uri}}})[0]
    assert [x["name"] for x in response["result"]] == ["add", "User"]
    assert response["result"][0]["range"]["start"]["line"] == 0


def test_workspace_symbol_search_is_deterministic_and_queryable():
    rpc = LSPJsonRpcServer()
    init(rpc)
    open_doc(rpc, "file:///tmp/b.sl", "function Beta():\n  return 1\n")
    open_doc(rpc, "file:///tmp/a.sl", "function Alpha():\n  return 1\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"workspace/symbol", "params":{"query":"alp"}})[0]
    assert [x["name"] for x in response["result"]] == ["Alpha"]
    assert response["result"][0]["location"]["uri"] == "file:///tmp/a.sl"


def test_definition_resolves_local_top_level_declaration():
    rpc = LSPJsonRpcServer()
    init(rpc)
    uri = "file:///tmp/def.sl"
    open_doc(rpc, uri, "function helper():\n  return 1\n\nlet value = helper()\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/definition", "params":{"textDocument":{"uri":uri}, "position":{"line":3,"character":14}}})[0]
    assert response["result"][0]["uri"] == uri
    assert response["result"][0]["range"]["start"]["line"] == 0


def test_navigation_unknown_document_returns_jsonrpc_error():
    rpc = LSPJsonRpcServer()
    init(rpc)
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/documentSymbol", "params":{"textDocument":{"uri":"file:///tmp/missing.sl"}}})[0]
    assert response["error"]["code"] == -32603


def test_definition_can_resolve_an_open_workspace_document():
    rpc = LSPJsonRpcServer()
    init(rpc)
    open_doc(rpc, "file:///tmp/lib.sl", "function helper():\n  return 1\n")
    uri = "file:///tmp/main.sl"
    open_doc(rpc, uri, "let value = helper()\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":3, "method":"textDocument/definition", "params":{"textDocument":{"uri":uri}, "position":{"line":0,"character":13}}})[0]
    assert response["result"][0]["uri"] == "file:///tmp/lib.sl"


def test_references_returns_all_open_document_name_references():
    rpc = LSPJsonRpcServer()
    init(rpc)
    uri = "file:///tmp/ref.sl"
    open_doc(rpc, uri, "function helper():\n  return 1\n\nlet value = helper()\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":4, "method":"textDocument/references", "params":{"textDocument":{"uri":uri}, "position":{"line":3,"character":14}, "context":{"includeDeclaration":True}}})[0]
    assert len(response["result"]) == 2
