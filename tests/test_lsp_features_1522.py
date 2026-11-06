from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_initialize_advertises_hover_and_completion():
    rpc = LSPJsonRpcServer()
    caps = init(rpc)[0]["result"]["capabilities"]
    assert caps["hoverProvider"] is True
    assert caps["completionProvider"]["triggerCharacters"] == ["."]


def test_hover_returns_function_signature():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/hover.sl"
    open_doc(rpc, uri, "function add(a: Number, b: Number) -> Number:\n  return a + b\n\nlet value = add(1, 2)\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/hover", "params":{"textDocument":{"uri":uri},"position":{"line":3,"character":13}}})[0]
    assert "function add(a: Number, b: Number) -> Number" in response["result"]["contents"]["value"]


def test_hover_unknown_symbol_returns_null():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/hover.sl"; open_doc(rpc, uri, "let value = unknown\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/hover", "params":{"textDocument":{"uri":uri},"position":{"line":0,"character":13}}})[0]
    assert response["result"] is None


def test_completion_returns_symbols_and_keywords_with_prefix():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/complete.sl"
    open_doc(rpc, uri, "function calculate(a: Number) -> Number:\n  return a\n\nlet value = 1\ncal\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/completion", "params":{"textDocument":{"uri":uri},"position":{"line":4,"character":3}}})[0]
    labels = [item["label"] for item in response["result"]["items"]]
    assert labels == ["calculate"]
    assert response["result"]["isIncomplete"] is False


def test_completion_includes_declared_record():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/complete.sl"
    open_doc(rpc, uri, "record User:\n  name: Text\n\nUs\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/completion", "params":{"textDocument":{"uri":uri},"position":{"line":3,"character":2}}})[0]
    assert response["result"]["items"][0]["label"] == "User"
    assert response["result"]["items"][0]["kind"] == 7
