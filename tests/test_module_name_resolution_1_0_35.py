from slang.core import parse_file, run, show_expr_value
from slang.diagnostics import diagnostics_for_source


def test_import_alias_resolves_exported_qualified_function(tmp_path):
    module = tmp_path / "math" / "basic" / "core.sl"
    module.parent.mkdir(parents=True)
    module.write_text('''module math.basic.core
export double
function double(x: Number) -> Number:
    return x * 2
''', encoding="utf-8")
    main = tmp_path / "main.sl"
    main.write_text('''module demo
import math.basic.core as m
let value = m.double(6)
show value
''', encoding="utf-8")
    program = parse_file(main)
    run(program)
    assert [show_expr_value(program, item) for item in program.show_exprs] == ["12"]


def test_named_import_resolves_exported_function(tmp_path):
    module = tmp_path / "math.sl"
    module.write_text('''module math
export double
function double(x: Number) -> Number:
    return x * 2
''', encoding="utf-8")
    main = tmp_path / "main.sl"
    main.write_text('''import math { double }
let value = double(7)
show value
''', encoding="utf-8")
    program = parse_file(main)
    run(program)
    assert [show_expr_value(program, item) for item in program.show_exprs] == ["14"]


def test_unknown_unqualified_name_is_reported_even_with_module_import():
    result = diagnostics_for_source('''let known = 1
let value = unknown_after_import
''', path="consumer.sl")
    diagnostic = next(item for item in result.diagnostics if item.code == "E2001")
    assert diagnostic.data == {"name": "unknown_after_import"}
