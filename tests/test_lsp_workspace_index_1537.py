from pathlib import Path

from slang.lsp_server import LSPServer
from slang.lsp_jsonrpc import LSPJsonRpcServer


def _uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_incremental_refresh_keeps_unchanged_program(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    a = root / "a.sl"
    b = root / "b.sl"
    a.write_text("let alpha = 1\n", encoding="utf-8")
    b.write_text("let beta = 2\n", encoding="utf-8")
    server = LSPServer(root_uri=_uri(root))
    server.initialize(root_uri=_uri(root))
    programs_before = dict(server._workspace_index_programs)
    b.write_text("let beta = 3\n", encoding="utf-8")
    server.refresh_workspace_files([_uri(b)])
    assert server._workspace_index_programs[_uri(a)][0] is programs_before[_uri(a)][0]
    assert server._workspace_index_programs[_uri(b)][0] is not programs_before[_uri(b)][0]


def test_deleted_file_is_removed_incrementally(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    target = root / "gone.sl"
    target.write_text("let gone = 1\n", encoding="utf-8")
    server = LSPServer(root_uri=_uri(root))
    server.initialize(root_uri=_uri(root))
    uri = _uri(target)
    assert uri in server._workspace_index_programs
    target.unlink()
    server.refresh_workspace_files([uri])
    assert uri not in server._workspace_index_programs
    assert uri not in server._workspace_index


def test_watched_files_notification_updates_index(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    target = root / "watched.sl"
    target.write_text("let old_name = 1\n", encoding="utf-8")
    server = LSPServer(root_uri=_uri(root))
    server.initialize(root_uri=_uri(root))
    target.write_text("let new_name = 1\n", encoding="utf-8")
    dispatcher = LSPJsonRpcServer(server)
    dispatcher.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": _uri(root)}})
    result = dispatcher.handle_message({"jsonrpc": "2.0", "method": "workspace/didChangeWatchedFiles", "params": {"changes": [{"uri": _uri(target), "type": 2}]}})
    assert result == ()
    names = {item["name"] for item in server.workspace_symbols("new")}
    assert "new_name" in names


def test_open_document_remains_authoritative_after_watcher_event(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    target = root / "open.sl"
    target.write_text("let disk_name = 1\n", encoding="utf-8")
    uri = _uri(target)
    server = LSPServer(root_uri=_uri(root))
    server.initialize(root_uri=_uri(root))
    server.did_open(uri, "let open_name = 1\n", version=1)
    target.write_text("let changed_disk_name = 1\n", encoding="utf-8")
    server.did_change_watched_files([{"uri": uri, "type": 2}])
    assert {item["name"] for item in server.workspace_symbols("open")} == {"open_name"}
    assert "changed_disk_name" not in {item["name"] for item in server.workspace_symbols("changed")}
