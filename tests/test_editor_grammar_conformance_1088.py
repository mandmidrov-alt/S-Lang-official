"""Static alignment checks for editor grammars and publication manifests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAMMARS = [
    ROOT / "editors/zed-slang/tree-sitter-slang/grammar.js",
    ROOT / "packaging/editor-publication/S-Lang-zed/tree-sitter-slang/grammar.js",
    ROOT / "packaging/editor-publication/tree-sitter-slang/grammar.js",
]


def test_all_zed_grammar_copies_are_identical():
    contents = [path.read_text(encoding="utf-8") for path in GRAMMARS]
    assert contents[0] == contents[1] == contents[2]


def test_tree_sitter_pipeline_covers_documented_shorthand_and_conditional_forms():
    grammar = GRAMMARS[0].read_text(encoding="utf-8")
    assert "pipeline_predicate" in grammar
    assert "pipeline_value" in grammar
    assert "conditional_pipeline_stage" in grammar
    assert "pipeline_branch" in grammar
    assert "seq('.', $.identifier" in grammar
    assert "choice('==', '!=', '<', '>', '<=', '>=', '+', '-', '*', '/', '%')" in grammar


def test_vscode_publication_manifest_declares_every_registered_configure_command():
    for relative in (
        "editors/vscode-slang/package.json",
        "packaging/editor-publication/S-Lang-vscode/package.json",
    ):
        package = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        commands = {item["command"] for item in package["contributes"]["commands"]}
        assert "slang.configureServerPath" in commands
