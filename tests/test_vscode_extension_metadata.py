import json
from pathlib import Path


def test_vscode_extension_activates_for_slang_documents_and_projects():
    package = json.loads(
        (Path(__file__).parents[1] / "editors" / "vscode-slang" / "package.json").read_text(encoding="utf-8")
    )
    events = package.get("activationEvents", [])
    assert "onLanguage:slang" in events
    assert "workspaceContains:slang.toml" in events


def test_vscode_extension_selects_slang_documents_for_language_server():
    source = (
        Path(__file__).parents[1] / "editors" / "vscode-slang" / "extension.js"
    ).read_text(encoding="utf-8")
    assert 'language: "slang"' in source
    assert '"S-Lang Language Server"' in source
    assert "traceOutputChannel: outputChannel" in source
