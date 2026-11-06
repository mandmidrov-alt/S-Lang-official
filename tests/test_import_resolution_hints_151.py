from slang.diagnostics import diagnostics_for_source


def test_missing_import_has_path_resolution_hint(tmp_path):
    result = diagnostics_for_source('import "missing.sl"\n', base_dir=tmp_path)
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "E1000"
    assert "Check the path in the import statement" in diagnostic.hint
    assert ".sl extension" in diagnostic.hint


def test_missing_reexport_source_has_specific_hint(tmp_path):
    result = diagnostics_for_source('export helper from "missing.sl"\n', base_dir=tmp_path)
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "E1000"
    assert "Check the path after the export declaration" in diagnostic.hint


def test_import_of_non_public_name_has_export_hint(tmp_path):
    (tmp_path / "library.sl").write_text(
        'module library\nexport visible\nfunction visible() -> Number:\n    return 1\nfunction hidden() -> Number:\n    return 2\n',
        encoding="utf-8",
    )
    result = diagnostics_for_source('import "library.sl" {hidden}\n', base_dir=tmp_path)
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "E1000"
    assert "not available through this module's public interface" in diagnostic.hint


def test_cyclic_import_has_actionable_hint(tmp_path):
    (tmp_path / "a.sl").write_text('import "b.sl"\n', encoding="utf-8")
    (tmp_path / "b.sl").write_text('import "a.sl"\n', encoding="utf-8")
    result = diagnostics_for_source('import "a.sl"\n', base_dir=tmp_path)
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "E1000"
    assert "import one another in a cycle" in diagnostic.hint


def test_unrelated_parse_error_keeps_existing_hint_behavior():
    result = diagnostics_for_source('this is not valid syntax\n')
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "E1000"
    assert diagnostic.hint != "Check the path in the import statement, including its spelling and .sl extension. Relative imports are resolved from the importing file's directory and project source roots."
