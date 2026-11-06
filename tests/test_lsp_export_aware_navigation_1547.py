from pathlib import Path

from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_definition_respects_transitive_public_api(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("export deep\nfunction deep():\n    return 1\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport deep\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = deep()\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    result = server.definition(uri(app), 1, 13)
    assert any(item["uri"] == uri(base) for item in result)


def test_definition_does_not_cross_private_transitive_boundary(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("function hidden():\n    return 1\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport middle\nfunction middle():\n    return 1\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = hidden()\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    result = server.definition(uri(app), 1, 13)
    assert not any(item["uri"] == uri(base) for item in result)


def test_hover_resolves_public_transitive_declaration(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("export deep\nfunction deep(value: Number) -> Number:\n    return value\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport deep\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = deep(1)\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    result = server.hover(uri(app), 1, 14)
    assert result is not None
    assert "deep(value: Number) -> Number" in result["contents"]["value"]


def test_references_use_each_document_export_boundary(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("export deep\nfunction deep():\n    return 1\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport deep\nlet local = deep()\n', encoding="utf-8")
    app.write_text('import "middle.sl"\nlet value = deep()\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(app), app.read_text(encoding="utf-8"))
    refs = server.references(uri(app), 1, 15, include_declaration=True)
    uris = {item["uri"] for item in refs}
    assert uri(base) in uris
    assert uri(middle) in uris
    assert uri(app) in uris


def test_document_symbols_remain_local_to_document(tmp_path):
    provider = tmp_path / "provider.sl"
    consumer = tmp_path / "consumer.sl"
    provider.write_text("export helper\nfunction helper():\n    return 1\n", encoding="utf-8")
    consumer.write_text('import "provider.sl"\nlet value = helper()\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path)); server.initialize(); server.did_open(uri(consumer), consumer.read_text(encoding="utf-8"))
    names = {item["name"] for item in server.document_symbols(uri(consumer))}
    assert "helper" not in names
