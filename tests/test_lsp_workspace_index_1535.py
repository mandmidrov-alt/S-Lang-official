from pathlib import Path
from slang import LSPServer


def file_uri(path):
    return path.resolve().as_uri()


def test_initialize_indexes_closed_workspace_sl_files(tmp_path):
    (tmp_path / "lib.sl").write_text("function closed_helper():\n  return 1\n", encoding="utf-8")
    server = LSPServer(root_uri=file_uri(tmp_path))
    result = server.initialize()
    assert result["serverInfo"]["version"] == "1.0"
    symbols = server.workspace_symbols("closed_helper")
    assert [item["name"] for item in symbols] == ["closed_helper"]
    assert symbols[0]["location"]["uri"] == file_uri(tmp_path / "lib.sl")


def test_open_document_overrides_closed_workspace_index(tmp_path):
    path = tmp_path / "lib.sl"
    path.write_text("function disk_name():\n  return 1\n", encoding="utf-8")
    server = LSPServer(root_uri=file_uri(tmp_path))
    server.initialize()
    server.did_open(file_uri(path), "function live_name():\n  return 1\n")
    assert server.workspace_symbols("disk_name") == ()
    assert [item["name"] for item in server.workspace_symbols("live_name")] == ["live_name"]


def test_definition_can_target_closed_workspace_file(tmp_path):
    lib = tmp_path / "lib.sl"
    lib.write_text("function closed_helper():\n  return 1\n", encoding="utf-8")
    main = tmp_path / "main.sl"
    main_uri = file_uri(main)
    server = LSPServer(root_uri=file_uri(tmp_path))
    server.initialize()
    server.did_open(main_uri, "let value = closed_helper()\n")
    result = server.definition(main_uri, 0, 15)
    assert result[0]["uri"] == file_uri(lib)
    assert result[0]["range"]["start"]["line"] == 0


def test_workspace_folder_change_refreshes_closed_file_index(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    path = root / "new.sl"
    path.write_text("function indexed_name():\n  return 1\n", encoding="utf-8")
    server = LSPServer()
    server.initialize()
    server.did_change_workspace_folders({"added": [{"uri": file_uri(root), "name": "project"}], "removed": []})
    assert [item["name"] for item in server.workspace_symbols("indexed_name")] == ["indexed_name"]
