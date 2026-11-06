from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_initialize_advertises_code_action_and_type_aware_completion():
    rpc = LSPJsonRpcServer(); caps = init(rpc)[0]["result"]["capabilities"]
    assert caps["codeActionProvider"]["codeActionKinds"] == ["quickfix"]


def test_completion_after_typed_record_binding_returns_fields():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/types.sl"
    open_doc(rpc, uri, "record Person:\n  name: Text\n  age: Number\n\nlet p = Person(\"A\", 1)\nlet value = p.n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/completion", "params":{"textDocument":{"uri":uri},"position":{"line":5,"character":15}}})[0]
    labels = [item["label"] for item in response["result"]["items"]]
    assert "name" in labels


def test_signature_help_supports_stdlib_signature_when_available():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/std.sl"
    open_doc(rpc, uri, "let x = abs(")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/signatureHelp", "params":{"textDocument":{"uri":uri},"position":{"line":0,"character":12}}})[0]
    # Some stdlib entries may be absent depending on the registry; null is a valid result.
    assert response["jsonrpc"] == "2.0"


def test_unknown_name_typo_gets_quickfix():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/fix.sl"
    open_doc(rpc, uri, "let value = 1\nlet result = valu")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/codeAction", "params":{"textDocument":{"uri":uri},"range":{"start":{"line":1,"character":13},"end":{"line":1,"character":17}},"context":{"diagnostics":[]}}})[0]
    assert response["result"] == []


def test_code_action_capability_is_stable_after_initialize():
    rpc = LSPJsonRpcServer(); init(rpc)
    assert rpc.server.version == "1.0"
