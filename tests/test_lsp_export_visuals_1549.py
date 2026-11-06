from pathlib import Path
from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def open_project(server, source: Path):
    server.initialize(root_uri=source.parent.resolve().as_uri())
    server.did_open(uri(source), source.read_text(), version=1)
    return uri(source)


def test_document_highlight_is_semantic_not_textual(tmp_path):
    source = tmp_path / "main.sl"
    source.write_text("let target = 1\nlet other = target + target\n")
    server = LSPServer(root_uri=tmp_path.resolve().as_uri())
    u = open_project(server, source)
    highlights = server.document_highlight(u, 1, 13)
    assert len(highlights) == 3


def test_transitive_public_import_is_highlighted(tmp_path):
    (tmp_path / "c.sl").write_text("export public_api\nfunction public_api() -> Number:\n    return 1\nfunction private_api() -> Number:\n    return 2\n")
    (tmp_path / "b.sl").write_text('import "c.sl"\nexport public_api\n')
    source = tmp_path / "a.sl"
    source.write_text('import "b.sl"\nfunction main() -> Number:\n    return public_api()\n')
    server = LSPServer(root_uri=tmp_path.resolve().as_uri())
    u = open_project(server, source)
    highlights = server.document_highlight(u, 2, 11)
    assert highlights


def test_private_transitive_symbol_is_not_highlighted(tmp_path):
    (tmp_path / "c.sl").write_text("export public_api\nfunction public_api() -> Number:\n    return 1\nfunction private_api() -> Number:\n    return 2\n")
    (tmp_path / "b.sl").write_text('import "c.sl"\nexport public_api\n')
    source = tmp_path / "a.sl"
    source.write_text('import "b.sl"\nfunction main() -> Number:\n    return private_api()\n')
    server = LSPServer(root_uri=tmp_path.resolve().as_uri())
    u = open_project(server, source)
    assert server.document_highlight(u, 2, 11) == ()


def test_semantic_tokens_classify_visible_imported_function(tmp_path):
    (tmp_path / "c.sl").write_text("export public_api\nfunction public_api() -> Number:\n    return 1\n")
    source = tmp_path / "a.sl"
    source.write_text('import "c.sl"\nfunction main() -> Number:\n    return public_api()\n')
    server = LSPServer(root_uri=tmp_path.resolve().as_uri())
    u = open_project(server, source)
    payload = server.semantic_tokens(u)
    assert 2 in payload["data"]
