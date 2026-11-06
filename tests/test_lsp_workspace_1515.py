from slang import LSPServer


def test_initialize_tracks_workspace_and_interfile_dependencies():
    server = LSPServer()
    result = server.initialize(root_uri="file:///tmp/project", workspace_folders=[{"uri": "file:///tmp/project", "name": "project"}])
    # This server publishes push diagnostics; do not advertise the unsupported
    # LSP pull-diagnostics protocol merely to expose inter-file dependency data.
    assert "diagnosticProvider" not in result["capabilities"]
    assert result["capabilities"]["textDocumentSync"]["openClose"] is True
    assert server.root_uri == "file:///tmp/project"
    assert server.workspace_folders[0]["name"] == "project"


def test_opened_dependency_builds_forward_and_reverse_graph(tmp_path):
    dep = tmp_path / "base.sl"
    dep.write_text("let value = 1\n", encoding="utf-8")
    app = tmp_path / "app.sl"
    app.write_text(f'import base\nlet x = value\n', encoding="utf-8")
    dep_uri = dep.resolve().as_uri()
    app_uri = app.resolve().as_uri()
    server = LSPServer()
    server.initialize(root_uri=tmp_path.resolve().as_uri())
    server.did_open(dep_uri, dep.read_text(), version=1)
    server.did_open(app_uri, app.read_text(), version=1)
    assert server.dependencies(app_uri) == (dep_uri,)
    assert server.dependents(dep_uri) == (app_uri,)


def test_dependency_change_returns_publications_for_dependents(tmp_path):
    dep = tmp_path / "base.sl"
    app = tmp_path / "app.sl"
    dep.write_text('let value = 1\n', encoding='utf-8')
    app.write_text('import base\nlet x = value\n', encoding='utf-8')
    dep_uri, app_uri = dep.resolve().as_uri(), app.resolve().as_uri()
    server = LSPServer()
    server.initialize(root_uri=tmp_path.resolve().as_uri())
    server.did_open(dep_uri, dep.read_text(), version=1)
    server.did_open(app_uri, app.read_text(), version=1)
    publications = server.did_change_publications(dep_uri, 'let value = "broken"\n', version=2)
    assert [item["uri"] for item in publications] == [dep_uri, app_uri]
    assert publications[0]["version"] == 2
    assert publications[1]["uri"] == app_uri


def test_close_removes_dependency_graph_edges(tmp_path):
    dep = tmp_path / "base.sl"
    app = tmp_path / "app.sl"
    dep.write_text('let value = 1\n', encoding='utf-8')
    app.write_text('import base\nlet x = value\n', encoding='utf-8')
    dep_uri, app_uri = dep.resolve().as_uri(), app.resolve().as_uri()
    server = LSPServer()
    server.did_open(dep_uri, dep.read_text())
    server.did_open(app_uri, app.read_text())
    server.did_close(dep_uri)
    assert server.dependencies(app_uri) == ()
    assert server.dependents(app_uri) == ()
