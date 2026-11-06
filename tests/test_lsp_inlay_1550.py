from pathlib import Path
from urllib.parse import quote

from slang.lsp_jsonrpc import LSPJsonRpcServer
from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_inlay_hints_parameter_names_are_deterministic(tmp_path):
    source = "function add(left: Number, right: Number) -> Number:\n    return left + right\n\nlet total = add(1, 2)\n"
    path = tmp_path / "main.sl"
    path.write_text(source, encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize(root_uri=uri(tmp_path))
    u = uri(path)
    server.did_open(u, source, version=1)
    hints = server.inlay_hints(u, range_start={"line": 0, "character": 0}, range_end={"line": 10, "character": 0})
    assert hints == (
        {"position": {"line": 3, "character": 4}, "label": "left: ", "kind": 2, "paddingRight": False},
        {"position": {"line": 3, "character": 7}, "label": "right: ", "kind": 2, "paddingRight": False},
    )


def test_inlay_hints_respect_requested_range(tmp_path):
    source = "function add(left: Number, right: Number) -> Number:\n    return left + right\n\nlet total = add(1, 2)\n"
    path = tmp_path / "main.sl"
    path.write_text(source, encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize(root_uri=uri(tmp_path))
    u = uri(path)
    server.did_open(u, source, version=1)
    hints = server.inlay_hints(u, range_start={"line": 3, "character": 5}, range_end={"line": 3, "character": 9})
    assert hints == ({"position": {"line": 3, "character": 7}, "label": "right: ", "kind": 2, "paddingRight": False},)


def test_inlay_hints_are_exposed_over_json_rpc(tmp_path):
    source = "function add(left: Number, right: Number) -> Number:\n    return left + right\n\nlet total = add(1, 2)\n"
    path = tmp_path / "main.sl"
    path.write_text(source, encoding="utf-8")
    rpc = LSPJsonRpcServer(LSPServer())
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": uri(tmp_path)}})
    rpc.handle_message({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri(path), "languageId": "slang", "version": 1, "text": source}}})
    result = rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "textDocument/inlayHint", "params": {"textDocument": {"uri": uri(path)}, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 10, "character": 0}}}})
    assert result[0]["result"][0]["label"] == "left: "
    assert result[0]["result"][1]["label"] == "right: "
