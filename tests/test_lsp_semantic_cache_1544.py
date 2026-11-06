from pathlib import Path

from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_workspace_semantic_cache_reused_until_project_change(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    module = root / "module.sl"
    module.write_text("function old_name():\n  return 1\n", encoding="utf-8")
    server = LSPServer(root_uri=uri(root))
    server.initialize(root_uri=uri(root))
    first = server._parsed_workspace()
    second = server._parsed_workspace()
    assert first is second
    symbols_first = server._semantic_symbols()
    symbols_second = server._semantic_symbols()
    assert symbols_first is symbols_second


def test_watcher_invalidates_semantic_cache_for_closed_file(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    module = root / "module.sl"
    module.write_text("function old_name():\n  return 1\n", encoding="utf-8")
    server = LSPServer(root_uri=uri(root))
    server.initialize(root_uri=uri(root))
    old_workspace = server._parsed_workspace()
    old_symbols = server._semantic_symbols()
    module.write_text("function new_name():\n  return 1\n", encoding="utf-8")
    server.did_change_watched_files([{"uri": uri(module), "type": 2}])
    new_workspace = server._parsed_workspace()
    new_symbols = server._semantic_symbols()
    assert new_workspace is not old_workspace
    assert new_symbols is not old_symbols
    assert "new_name" in {item.name for item in new_symbols}
    assert "old_name" not in {item.name for item in new_symbols}


def test_definition_uses_invalidated_workspace_semantic_state(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    provider = root / "provider.sl"
    consumer = root / "consumer.sl"
    provider.write_text("function old_name():\n  return 1\n", encoding="utf-8")
    consumer.write_text('import "provider"\nlet value = old_name()\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(root))
    server.initialize(root_uri=uri(root))
    server.did_open(uri(consumer), consumer.read_text(encoding="utf-8"), version=1)
    first = server.definition(uri(consumer), 1, 17)
    assert any(item["uri"] == uri(provider) for item in first)
    provider.write_text("function new_name():\n  return 1\n", encoding="utf-8")
    server.did_change_watched_files([{"uri": uri(provider), "type": 2}])
    # The old declaration is gone from the indexed semantic state.
    assert not any(item["uri"] == uri(provider) for item in server.definition(uri(consumer), 1, 17))
    assert "new_name" in {item["name"] for item in server.workspace_symbols("new")}
