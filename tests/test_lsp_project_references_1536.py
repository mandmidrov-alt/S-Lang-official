from pathlib import Path
from slang import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_references_include_closed_workspace_files(tmp_path):
    lib = tmp_path / "lib.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    consumer = tmp_path / "main.sl"
    consumer_uri = uri(consumer)
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(consumer_uri, 'import "lib"\nlet value = helper()\n')
    refs = server.references(consumer_uri, 1, 15, include_declaration=True)
    assert any(item["uri"] == uri(lib) for item in refs)
    assert any(item["uri"] == consumer_uri for item in refs)


def test_rename_updates_closed_workspace_references(tmp_path):
    lib = tmp_path / "lib.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    consumer = tmp_path / "main.sl"
    consumer_uri = uri(consumer)
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(consumer_uri, 'import "lib"\nlet value = helper()\n')
    edit = server.rename(consumer_uri, 1, 15, "worker")
    assert edit is not None
    assert uri(lib) in edit["changes"]
    assert consumer_uri in edit["changes"]
    assert any(item["newText"] == "worker" for item in edit["changes"][uri(lib)])
    assert any(item["newText"] == "worker" for item in edit["changes"][consumer_uri])


def test_open_document_overrides_closed_reference_index(tmp_path):
    lib = tmp_path / "lib.sl"
    lib.write_text("function helper():\n  return 1\n", encoding="utf-8")
    main = tmp_path / "main.sl"
    main_uri = uri(main)
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(uri(lib), "function other():\n  return 1\n")
    server.did_open(main_uri, 'import "lib"\nlet value = helper()\n')
    refs = server.references(main_uri, 1, 15)
    assert all(item["uri"] != uri(lib) for item in refs)
