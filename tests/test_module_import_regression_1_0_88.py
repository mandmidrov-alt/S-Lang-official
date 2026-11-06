from pathlib import Path

import pytest

from slang.core import ParseError, parse_file, run, show_expr_value


def test_nested_transitive_and_selective_file_imports(tmp_path):
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "core.sl").write_text(
        '''module core
export add, triple
function add(left: Number, right: Number) -> Number:
    return left + right
function triple(value: Number) -> Number:
    return value * 3
function private_helper(value: Number) -> Number:
    return value * 100
''',
        encoding="utf-8",
    )
    (modules / "middle.sl").write_text(
        'module middle\nexport add from "core.sl"\n', encoding="utf-8"
    )
    (modules / "api.sl").write_text(
        'module public_api\nexport add from "middle.sl"\n', encoding="utf-8"
    )
    main = tmp_path / "main.sl"
    main.write_text(
        '''module demo
import "modules/api.sl" as api
import "modules/core.sl" { triple }
import "modules/core.sl" as direct
let transitive = api.add(10, 5)
let selective = triple(7)
let namespaced = direct.add(20, 22)
show transitive
show selective
show namespaced
''',
        encoding="utf-8",
    )

    program = parse_file(main)
    run(program)
    assert [show_expr_value(program, item) for item in program.show_exprs] == [
        "15", "21", "42"
    ]


def test_private_symbol_cannot_be_imported_from_file_module(tmp_path):
    (tmp_path / "library.sl").write_text(
        '''module library
export public_value
function public_value() -> Number:
    return 1
function private_value() -> Number:
    return 2
''',
        encoding="utf-8",
    )
    main = tmp_path / "main.sl"
    main.write_text(
        'import "library.sl" { private_value }\n', encoding="utf-8"
    )

    with pytest.raises(ParseError, match="does not publicly export"):
        parse_file(main)


def test_cyclic_file_import_is_rejected(tmp_path):
    (tmp_path / "first.sl").write_text(
        'module first\nimport "second.sl"\n', encoding="utf-8"
    )
    (tmp_path / "second.sl").write_text(
        'module second\nimport "first.sl"\n', encoding="utf-8"
    )

    with pytest.raises(ParseError, match="cyclic import"):
        parse_file(tmp_path / "first.sl")


def test_missing_file_import_is_reported(tmp_path):
    main = tmp_path / "main.sl"
    main.write_text('import "not_found.sl"\n', encoding="utf-8")

    with pytest.raises(ParseError, match="import not found"):
        parse_file(main)
