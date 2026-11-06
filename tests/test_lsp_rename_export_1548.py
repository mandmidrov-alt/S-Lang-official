from pathlib import Path

from slang import LSPServer
from slang.diagnostics import Diagnostic, DiagnosticSeverity
from slang.diagnostics import SourcePosition, SourceSpan


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_prepare_rename_respects_transitive_export_boundary(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("export deep\nfunction deep():\n  return 1\nfunction private():\n  return 2\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport deep\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(uri(app), 'import "middle.sl"\nlet value = deep()\n')
    prepared = server.prepare_rename(uri(app), 1, 14)
    assert prepared is not None
    assert prepared["placeholder"] == "deep"


def test_rename_updates_only_documents_where_exported_symbol_is_visible(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    public_app = tmp_path / "public.sl"
    private_app = tmp_path / "private.sl"
    base.write_text("export deep\nfunction deep():\n  return 1\nfunction hidden():\n  return 2\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport deep\n', encoding="utf-8")
    public_app.write_text('import "middle.sl"\nlet value = deep()\n', encoding="utf-8")
    private_app.write_text('import "middle.sl"\nlet value = hidden()\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(uri(public_app), public_app.read_text(encoding="utf-8"))
    edit = server.rename(uri(public_app), 1, 13, "deeper")
    assert edit is not None
    assert uri(base) in edit["changes"]
    assert uri(public_app) in edit["changes"]
    assert uri(private_app) not in edit["changes"]


def test_code_action_can_fix_typo_to_public_transitive_import(tmp_path):
    base = tmp_path / "base.sl"
    middle = tmp_path / "middle.sl"
    app = tmp_path / "app.sl"
    base.write_text("export helper\nfunction helper():\n  return 1\n", encoding="utf-8")
    middle.write_text('import "base.sl"\nexport helper\n', encoding="utf-8")
    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    app_uri = uri(app)
    server.did_open(app_uri, 'import "middle.sl"\nlet value = helpr()\n')
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        message="unknown name 'helpr'",
        code="E2001",
        phase="semantic",
        span=SourceSpan(SourcePosition(2, 13), SourcePosition(2, 18)),
        path=app_uri,
        data={"name": "helpr"},
    )
    actions = server.code_actions(app_uri, diagnostics=(diagnostic,))
    assert any("helper" in action.get("title", "") for action in actions)
