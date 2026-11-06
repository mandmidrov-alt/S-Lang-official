import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VSCODE = ROOT / "editors" / "vscode-slang"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_vscode_extension_metadata_is_valid():
    package = _json(VSCODE / "package.json")
    assert package["name"] == "slang-language"
    assert re.fullmatch(r"\d+\.\d+\.\d+", package["version"])
    assert package["main"] == "extension.js"
    assert package["contributes"]["languages"][0]["id"] == "slang"
    assert ".sl" in package["contributes"]["languages"][0]["extensions"]
    assert "vscode-languageclient" in package["dependencies"]


def test_vscode_language_configuration_and_grammar_are_valid():
    language = _json(VSCODE / "language-configuration.json")
    grammar = _json(VSCODE / "syntaxes" / "slang.tmLanguage.json")
    snippets = _json(VSCODE / "snippets" / "slang.json")

    assert language["comments"]["lineComment"] == "#"
    assert grammar["scopeName"] == "source.slang"
    assert snippets


def test_vscode_extension_uses_canonical_slang_lsp_command():
    extension = (VSCODE / "extension.js").read_text(encoding="utf-8")
    assert '["lsp"]' in extension
    assert '"slang.serverPath"' in (VSCODE / "package.json").read_text(encoding="utf-8")


def test_editor_documentation_points_to_lsp_and_vscode_extension():
    text = (ROOT / "editors" / "README.md").read_text(encoding="utf-8")
    assert "slang lsp" in text
    assert "editors/vscode-slang/" in text


def test_vscode_extension_exposes_project_workflow():
    package = _json(VSCODE / "package.json")
    commands = {item["command"] for item in package["contributes"]["commands"]}
    assert "slang.runProject" in commands
    assert "slang.checkProject" in commands
    assert "slang.runProjectNativeJit" in commands
    assert package["contributes"]["taskDefinitions"][0]["type"] == "slang"


def test_vscode_extension_is_project_aware():
    package = _json(VSCODE / "package.json")
    extension = (VSCODE / "extension.js").read_text(encoding="utf-8")
    assert '"slang.toml"' in extension
    assert "projectEntry" in extension
    assert "registerTaskProvider" in extension
    assert "workspaceFolders" in extension
    assert '"project.autoStartLanguageServer"' in extension


def test_editor_workflow_packages_vsix_with_runtime_dependencies():
    workflow = (ROOT / ".github" / "workflows" / "editor-extension.yml").read_text(encoding="utf-8")
    package = (VSCODE / "package.json").read_text(encoding="utf-8")
    assert "npm install --no-audit --no-fund" in workflow
    assert '"package": "vsce package"' in package
    assert '"vscode-languageclient"' in package


def test_neovim_integration_has_canonical_lsp_and_project_workflow():
    nvim = ROOT / "editors" / "neovim-slang"
    assert (nvim / "plugin" / "slang.lua").is_file()
    assert (nvim / "ftdetect" / "slang.vim").is_file()
    assert (nvim / "ftplugin" / "slang.lua").is_file()
    assert (nvim / "README.md").is_file()
    syntax = (nvim / "syntax" / "slang.vim").read_text(encoding="utf-8")
    assert "syntax keyword slangKeyword" in syntax
    assert "|>" in syntax

    lsp = (nvim / "lua" / "slang" / "lsp.lua").read_text(encoding="utf-8")
    commands = (nvim / "lua" / "slang" / "commands.lua").read_text(encoding="utf-8")
    project = (nvim / "lua" / "slang" / "project.lua").read_text(encoding="utf-8")

    assert '"slang", "lsp"' in lsp
    assert '"slang.toml"' in lsp
    assert '"slang.toml"' in project
    assert '"--native-jit"' in commands
    assert '"check"' in commands
    assert '"init"' in commands


def test_zed_integration_has_valid_metadata_and_lsp_command():
    zed = ROOT / "editors" / "zed-slang"
    manifest = (zed / "extension.toml").read_text(encoding="utf-8")
    cargo = (zed / "Cargo.toml").read_text(encoding="utf-8")
    source = (zed / "src" / "lib.rs").read_text(encoding="utf-8")
    language = (zed / "languages" / "slang" / "config.toml").read_text(encoding="utf-8")
    grammar = (zed / "tree-sitter-slang" / "grammar.js").read_text(encoding="utf-8")
    readme = (zed / "README.md").read_text(encoding="utf-8")

    assert 'id = "slang"' in manifest
    assert 'name = "S-Lang"' in manifest
    assert '[language_servers.slang]' in manifest
    assert 'languages = ["S-Lang"]' in manifest
    assert '[grammars.slang]' in manifest
    assert 'zed_extension_api = "0.7"' in cargo
    assert '"slang".to_string()' in source
    assert '"lsp".to_string()' in source
    assert 'name = "S-Lang"' in language
    assert 'path_suffixes = ["sl"]' in language
    assert "name: 'slang'" in grammar
    assert "slang lsp" in readme


def test_emacs_integration_has_major_mode_and_eglot_workflow():
    emacs = ROOT / "editors" / "emacs-slang"
    mode = (emacs / "slang-mode.el").read_text(encoding="utf-8")
    readme = (emacs / "README.md").read_text(encoding="utf-8")

    assert "define-derived-mode slang-mode" in mode
    assert '\\.sl' in mode
    assert "(require 'eglot)" in mode
    assert '[eglot-server-programs' not in mode  # registration is done dynamically
    assert '(list slang-server-command "lsp")' in mode
    assert "slang-run-project-native-jit" in mode
    assert "slang.toml" in mode or "slang--project-root" in mode
    assert "Eglot" in readme
    assert "slang lsp" in readme


def test_editor_package_builder_and_distribution_workflow_exist():
    builder = ROOT / "packaging" / "build-editor-packages.py"
    workflow = ROOT / ".github" / "workflows" / "editor-packages.yml"
    assert builder.is_file()
    assert workflow.is_file()
    builder_text = builder.read_text(encoding="utf-8")
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "S-Lang-Neovim-{0}.zip" in builder_text
    assert "slang-mode-{0}.tar.gz" in builder_text
    assert "S-Lang-Zed-{0}.zip" in builder_text
    assert "vsce package" in builder_text
    assert "npm run package" in workflow_text
    assert "--version 1.0.0" in workflow_text
    assert "dist/editors/*" in workflow_text


def test_editor_publication_metadata_is_present():
    publishing = ROOT / "packaging" / "editor-publishing" / "PUBLISHING.md"
    vscode = ROOT / "editors" / "vscode-slang"
    emacs_mode = ROOT / "editors" / "emacs-slang" / "slang-mode.el"
    assert publishing.exists()
    assert (vscode / "CHANGELOG.md").exists()
    assert (vscode / "LICENSE").exists()
    text = emacs_mode.read_text(encoding="utf-8")
    assert ";; Version: 1.0.0" in text
    assert "Package-Requires" in text


def test_editor_branding_icon_is_present_and_declared():
    icon = ROOT / "branding" / "s-lang-editor-icon.png"
    vscode_icon = VSCODE / "icon.png"
    publication_icon = ROOT / "packaging" / "editor-publication" / "S-Lang-vscode" / "icon.png"
    assert icon.is_file()
    assert vscode_icon.is_file()
    assert publication_icon.is_file()
    package = _json(VSCODE / "package.json")
    assert package["icon"] == "icon.png"


def test_publication_repository_plan_and_sync_tool_exist():
    plan = ROOT / "packaging" / "editor-publication" / "REPOSITORIES.md"
    sync = ROOT / "packaging" / "sync-editor-publication.py"
    assert plan.is_file()
    assert sync.is_file()
    plan_text = plan.read_text(encoding="utf-8")
    sync_text = sync.read_text(encoding="utf-8")
    for name in ("S-Lang-vscode", "S-Lang-neovim", "S-Lang-zed", "tree-sitter-slang", "slang-mode"):
        assert name in plan_text
    assert "slang lsp" in sync_text
