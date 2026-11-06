from slang import LSPJsonRpcServer
from slang.core import parse
from slang.diagnostics import Diagnostic, DiagnosticSeverity, SourcePosition, SourceSpan
from slang.lsp_features import code_actions_for_diagnostics


def init(rpc):
    return rpc.handle_message({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def test_hover_shows_local_parameter_type():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/local.sl"
    open_doc(rpc, uri, "function add(a: Number, b: Text) -> Number:\n  return a\n\nlet value = add(1, \"x\")\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/hover", "params":{"textDocument":{"uri":uri},"position":{"line":1,"character":9}}})[0]
    assert "a: Number" in response["result"]["contents"]["value"]


def test_completion_includes_function_parameters():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/local.sl"
    open_doc(rpc, uri, "function add(a: Number, b: Text) -> Number:\n  return a\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/completion", "params":{"textDocument":{"uri":uri},"position":{"line":1,"character":9}}})[0]
    items = {item["label"]: item for item in response["result"]["items"]}
    assert items["a"]["kind"] == 6
    assert "Number" in items["a"]["detail"]


def test_hover_shows_expression_type():
    rpc = LSPJsonRpcServer(); init(rpc)
    uri = "file:///tmp/type.sl"
    open_doc(rpc, uri, "let value = 1 + 2\n")
    response = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/hover", "params":{"textDocument":{"uri":uri},"position":{"line":0,"character":13}}})[0]
    assert response["result"]["contents"]["value"].strip().endswith("Number\n```")


def test_unknown_field_typo_quickfix_is_safe_and_deterministic():
    program = parse("record User:\n  name: Text\n  age: Number\n\nlet user = User(\"A\", 20)\n")
    diagnostic = Diagnostic(
        DiagnosticSeverity.ERROR,
        "unknown field 'nmae' on User",
        code="E2005",
        phase="semantic",
        span=SourceSpan(SourcePosition(6, 13), SourcePosition(6, 17)),
        data={"field":"nmae", "base_type":"User"},
    )
    actions = code_actions_for_diagnostics(program, "", "file:///tmp/fix.sl", (diagnostic,))
    assert len(actions) == 1
    assert actions[0]["title"] == "Replace field 'nmae' with 'name'"
    assert actions[0]["edit"]["changes"]["file:///tmp/fix.sl"][0]["newText"] == "name"
