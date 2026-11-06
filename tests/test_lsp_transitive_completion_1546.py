from pathlib import Path

from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def labels(items):
    return {item["label"] for item in items}


def test_completion_traverses_transitive_imports(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("function deep(value: Number) -> Number:\n    return value\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nfunction middle(value: Number) -> Number:\n    return deep(value)\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = dee\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    assert "deep" in labels(server.completion(uri(app), 1, 15))


def test_signature_help_traverses_transitive_imports(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("function deep(value: Number, text: Text) -> Number:\n    return value\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nfunction middle(value: Number) -> Number:\n    return deep(value, "x")\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = deep(1, )\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    result = server.signature_help(uri(app), 1, 20)
    assert result is not None
    assert "deep(value: Number, text: Text) -> Number" in result["signatures"][0]["label"]


def test_explicit_intermediate_exports_block_private_transitive_declaration(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("function deep(value: Number) -> Number:\n    return value\n", encoding="utf-8")
    middle.write_text('export middle\nimport "base.sl"\nfunction middle(value: Number) -> Number:\n    return deep(value)\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = m\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    items = labels(server.completion(uri(app), 1, 13))
    assert "deep" not in items
    assert "middle" in items
