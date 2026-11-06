import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_vscode_grammar_is_valid_and_covers_1088_language_surface():
    grammar = json.loads((ROOT / "editors/vscode-slang/syntaxes/slang.tmLanguage.json").read_text(encoding="utf-8"))
    text = json.dumps(grammar)
    for token in ("function", "record", "entity", "property", "module", "import", "export", "sequence", "graph", "physics", "where", "map", "sort", "reduce", "average", "tee", "satisfy", "minimizing", "maximizing", "|>"):
        assert token in text


def test_zed_grammar_and_highlights_cover_1088_language_surface():
    grammar = (ROOT / "editors/zed-slang/tree-sitter-slang/grammar.js").read_text(encoding="utf-8")
    highlights = (ROOT / "editors/zed-slang/languages/slang/highlights.scm").read_text(encoding="utf-8")
    for token in ("function_declaration", "record_declaration", "entity_declaration", "pipeline_expression", "pipeline_stage", "sequence_statement", "graph_declaration", "satisfy_statement", "import_declaration", "export_declaration"):
        assert token in grammar
    for token in ('"function"', '"record"', '"entity"', '"sequence"', '"where"', '"map"', '"sort"', '"reduce"', '"satisfy"'):
        assert token in highlights


def test_editor_versions_are_aligned_to_slang_1088():
    vscode = json.loads((ROOT / "editors/vscode-slang/package.json").read_text(encoding="utf-8"))
    zed = json.loads((ROOT / "editors/zed-slang/tree-sitter-slang/package.json").read_text(encoding="utf-8"))
    emacs = (ROOT / "editors/emacs-slang/slang-mode.el").read_text(encoding="utf-8")
    assert vscode["version"] == "1.0.0"
    assert zed["version"] == "1.0.0"
    assert "Version: 1.0.0" in emacs


def test_zed_grammar_copies_are_identical_and_do_not_advertise_unsupported_loops():
    paths = [
        ROOT / "editors/zed-slang/tree-sitter-slang/grammar.js",
        ROOT / "packaging/editor-publication/tree-sitter-slang/grammar.js",
        ROOT / "packaging/editor-publication/S-Lang-zed/tree-sitter-slang/grammar.js",
    ]
    contents = [path.read_text(encoding="utf-8") for path in paths]
    assert contents[0] == contents[1] == contents[2]
    grammar = contents[0]
    assert "for_statement" not in grammar
    assert "while_statement" not in grammar
    assert "logical_or_expression" in grammar
    assert "logical_and_expression" in grammar
    assert "comparison_expression" in grammar
    assert "power_expression" in grammar
    assert "not_expression" in grammar
