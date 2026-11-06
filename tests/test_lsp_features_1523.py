from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_initialize_advertises_signature_help():
    rpc = LSPJsonRpcServer()
    caps = init(rpc)[0]["result"]["capabilities"]
    assert caps["signatureHelpProvider"]["triggerCharacters"] == ["(", ","]


def test_signature_help_reports_active_parameter():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/sig.sl"
    open_doc(rpc, uri, "function add(a: Number, b: Text) -> Number:\n  return 1\n\nlet x = add(1, \n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/signatureHelp", "params":{"textDocument":{"uri":uri},"position":{"line":3,"character":15}}})[0]
    result = response["result"]
    assert result["activeSignature"] == 0
    assert result["signatures"][0]["activeParameter"] == 1
    assert result["signatures"][0]["label"] == "function add(a: Number, b: Text) -> Number"
    assert result["signatures"][0]["parameters"][1]["label"] == "b: Text"


def test_signature_help_handles_nested_call_commas():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/sig.sl"
    open_doc(rpc, uri, "function outer(a: Number, b: Number) -> Number:\n  return a\n\nfunction inner(x: Number, y: Number) -> Number:\n  return x\n\nlet z = outer(inner(1, 2), ")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/signatureHelp", "params":{"textDocument":{"uri":uri},"position":{"line":6,"character":32}}})[0]
    assert response["result"]["signatures"][0]["activeParameter"] == 1


def test_signature_help_unknown_call_returns_null():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/sig.sl"; open_doc(rpc, uri, "let x = unknown(1, ")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/signatureHelp", "params":{"textDocument":{"uri":uri},"position":{"line":0,"character":20}}})[0]
    assert response["result"] is None
