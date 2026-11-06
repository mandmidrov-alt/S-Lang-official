from pathlib import Path

from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "version": 1, "text": text}}})


def test_initialize_advertises_document_link_provider():
    rpc = LSPJsonRpcServer()
    caps = init(rpc)[0]["result"]["capabilities"]
    assert caps["documentLinkProvider"] == {"resolveProvider": False}


def test_document_link_resolves_local_import(tmp_path):
    lib = tmp_path / "lib.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main = tmp_path / "main.sl"
    main.write_text('import "lib.sl"\nlet value = helper()\n', encoding="utf-8")
    rpc = LSPJsonRpcServer()
    init(rpc)
    open_doc(rpc, lib.as_uri(), lib.read_text(encoding="utf-8"))
    open_doc(rpc, main.as_uri(), main.read_text(encoding="utf-8"))
    result = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/documentLink", "params":{"textDocument":{"uri":main.as_uri()}}})[0]["result"]
    assert len(result) == 1
    assert result[0]["target"] == lib.resolve().as_uri()
    assert result[0]["range"] == {"start":{"line":0,"character":8},"end":{"line":0,"character":14}}


def test_document_link_uses_resolved_target_even_when_target_is_not_open(tmp_path):
    lib = tmp_path / "lib.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main = tmp_path / "main.sl"
    main.write_text('import "lib.sl"\n', encoding="utf-8")
    rpc = LSPJsonRpcServer()
    init(rpc)
    open_doc(rpc, main.as_uri(), main.read_text(encoding="utf-8"))
    result = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/documentLink", "params":{"textDocument":{"uri":main.as_uri()}}})[0]["result"]
    assert result[0]["target"] == lib.resolve().as_uri()


def test_document_link_skips_unresolved_and_std_imports(tmp_path):
    main = tmp_path / "main.sl"
    text = 'import "missing.sl"\nimport std.math\n'
    main.write_text(text, encoding="utf-8")
    rpc = LSPJsonRpcServer()
    init(rpc)
    open_doc(rpc, main.as_uri(), text)
    result = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/documentLink", "params":{"textDocument":{"uri":main.as_uri()}}})[0]["result"]
    assert result == []


def test_document_link_is_deterministic(tmp_path):
    a = tmp_path / "a.sl"
    b = tmp_path / "b.sl"
    main = tmp_path / "main.sl"
    a.write_text("function a():\n  return 1\n", encoding="utf-8")
    b.write_text("function b():\n  return 1\n", encoding="utf-8")
    text = 'import "b.sl"\nimport "a.sl"\n'
    main.write_text(text, encoding="utf-8")
    rpc = LSPJsonRpcServer()
    init(rpc)
    open_doc(rpc, a.as_uri(), a.read_text(encoding="utf-8"))
    open_doc(rpc, b.as_uri(), b.read_text(encoding="utf-8"))
    open_doc(rpc, main.as_uri(), text)
    result = rpc.handle_message({"jsonrpc":"2.0", "id":2, "method":"textDocument/documentLink", "params":{"textDocument":{"uri":main.as_uri()}}})[0]["result"]
    assert [item["target"] for item in result] == [b.resolve().as_uri(), a.resolve().as_uri()]
