from pathlib import Path
from slang.lsp_jsonrpc import LSPJsonRpcServer
from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_file_operation_capabilities_are_advertised():
    server = LSPServer()
    result = server.initialize()
    ops = result["capabilities"]["workspace"]["fileOperations"]
    assert all(name in ops for name in ("didCreate", "didRename", "didDelete"))
    assert ops["didCreate"]["filters"][0]["pattern"]["glob"] == "**/*.sl"


def test_create_and_delete_update_index(tmp_path):
    root = uri(tmp_path)
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    created = tmp_path / "new.sl"
    created.write_text("let value = 1\n", encoding="utf-8")
    assert uri(created) in server.did_create_files([{"uri": uri(created)}])
    created.unlink()
    server.did_delete_files([{"uri": uri(created)}])
    assert uri(created) not in server._workspace_index


def test_rename_replaces_old_index_entry(tmp_path):
    root = uri(tmp_path)
    old = tmp_path / "old.sl"
    new = tmp_path / "new.sl"
    old.write_text("let value = 1\n", encoding="utf-8")
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    assert uri(old) in server._workspace_index
    old.rename(new)
    server.did_rename_files([{"oldUri": uri(old), "newUri": uri(new)}])
    assert uri(old) not in server._workspace_index
    assert uri(new) in server._workspace_index


def test_jsonrpc_file_operations_are_notifications(tmp_path):
    root = uri(tmp_path)
    path = tmp_path / "created.sl"
    server = LSPJsonRpcServer(LSPServer(root_uri=root))
    server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": root}})
    path.write_text("let value = 1\n", encoding="utf-8")
    assert server.handle_message({"jsonrpc": "2.0", "method": "workspace/didCreateFiles", "params": {"files": [{"uri": uri(path)}]}}) == ()
    assert uri(path) in server.server._workspace_index
    path.rename(tmp_path / "renamed.sl")
    assert server.handle_message({"jsonrpc": "2.0", "method": "workspace/didRenameFiles", "params": {"files": [{"oldUri": uri(path), "newUri": uri(tmp_path / "renamed.sl")}]}}) == ()
    assert uri(path) not in server.server._workspace_index


def test_file_operations_refresh_closed_dependency_graph(tmp_path):
    root = uri(tmp_path)
    lib = tmp_path / "lib.sl"
    main = tmp_path / "main.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main.write_text('import "lib"\nlet value = helper()\n', encoding="utf-8")
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    assert uri(lib) in server._dependencies[uri(main)]
    lib.unlink()
    server.did_delete_files([{"uri": uri(lib)}])
    assert uri(lib) not in server._dependencies[uri(main)]


def test_file_rename_rebuilds_closed_dependency_graph(tmp_path):
    root = uri(tmp_path)
    old = tmp_path / "lib.sl"
    new = tmp_path / "renamed.sl"
    main = tmp_path / "main.sl"
    old.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main.write_text('import "lib"\nlet value = helper()\n', encoding="utf-8")
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    assert uri(old) in server._dependencies[uri(main)]
    old.rename(new)
    server.did_rename_files([{"oldUri": uri(old), "newUri": uri(new)}])
    assert uri(old) not in server._dependencies[uri(main)]


def test_file_create_rebuilds_closed_dependency_graph(tmp_path):
    root = uri(tmp_path)
    main = tmp_path / "main.sl"
    lib = tmp_path / "lib.sl"
    main.write_text('import "lib"\nlet value = helper()\n', encoding="utf-8")
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    assert server._dependencies.get(uri(main), ()) == ()
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    server.did_create_files([{"uri": uri(lib)}])
    assert uri(lib) in server._dependencies[uri(main)]


def test_file_operation_publications_include_open_documents_with_changed_dependencies(tmp_path):
    root = uri(tmp_path)
    main = tmp_path / "main.sl"
    lib = tmp_path / "lib.sl"
    main.write_text('import "lib"\nlet value = 1\n', encoding="utf-8")
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    server.did_open(uri(main), main.read_text(encoding="utf-8"), version=1)
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    publications = server.did_create_publications([{"uri": uri(lib)}])
    assert [item["uri"] for item in publications] == [uri(main)]
    assert publications[0]["version"] == 1


def test_jsonrpc_file_operation_publishes_affected_open_document(tmp_path):
    root = uri(tmp_path)
    main = tmp_path / "main.sl"
    lib = tmp_path / "lib.sl"
    main.write_text('import "lib"\nlet value = 1\n', encoding="utf-8")
    rpc = LSPJsonRpcServer(LSPServer(root_uri=root))
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": root}})
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri(main), "text": main.read_text(encoding="utf-8"), "version": 1}}})
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    result = rpc.handle_message({"jsonrpc": "2.0", "method": "workspace/didCreateFiles", "params": {"files": [{"uri": uri(lib)}]}})
    assert len(result) == 1
    assert result[0]["method"] == "textDocument/publishDiagnostics"
    assert result[0]["params"]["uri"] == uri(main)


def test_file_operation_invalidates_semantic_token_delta_history_for_impacted_document(tmp_path):
    root = uri(tmp_path)
    lib = tmp_path / "lib.sl"
    main = tmp_path / "main.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main.write_text('import "lib"\nlet value = helper()\n', encoding="utf-8")
    server = LSPServer(root_uri=root)
    server.initialize(root_uri=root)
    server.did_open(uri(main), main.read_text(encoding="utf-8"), version=1)
    first = server.semantic_tokens(uri(main))
    assert first["resultId"]
    lib.unlink()
    server.did_delete_files([{"uri": uri(lib)}])
    delta = server.semantic_tokens_delta(uri(main), first["resultId"])
    assert "edits" not in delta
    assert "data" in delta


def test_watcher_change_publishes_diagnostics_for_affected_open_document(tmp_path):
    root = uri(tmp_path)
    lib = tmp_path / "lib.sl"
    main = tmp_path / "main.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main.write_text('import "lib"\nlet value = helper()\n', encoding="utf-8")
    rpc = LSPJsonRpcServer(LSPServer(root_uri=root))
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": root}})
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri(main), "text": main.read_text(encoding="utf-8"), "version": 1}}})
    lib.unlink()
    result = rpc.handle_message({"jsonrpc": "2.0", "method": "workspace/didChangeWatchedFiles", "params": {"changes": [{"uri": uri(lib), "type": 3}]}})
    assert len(result) == 1
    assert result[0]["method"] == "textDocument/publishDiagnostics"
    assert result[0]["params"]["uri"] == uri(main)
