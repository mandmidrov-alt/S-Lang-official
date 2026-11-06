from slang.core import parse_file, run, show_expr_value


def test_transitive_reexport_preserves_public_api(tmp_path):
    (tmp_path / "base.sl").write_text('''module base
export double
function double(x: Number) -> Number:
    return x * 2
function hidden(x: Number) -> Number:
    return x * 9
''', encoding="utf-8")
    (tmp_path / "middle.sl").write_text('''module middle
export double from "base"
''', encoding="utf-8")
    (tmp_path / "api.sl").write_text('''module api
export double from "middle"
''', encoding="utf-8")
    (tmp_path / "main.sl").write_text('''module demo
import api { double }
let result = double(7)
show result
''', encoding="utf-8")

    program = parse_file(tmp_path / "main.sl")
    run(program)
    assert [show_expr_value(program, item) for item in program.show_exprs] == ["14"]


def test_same_module_can_be_imported_under_distinct_aliases(tmp_path):
    (tmp_path / "math.sl").write_text('''module math
export double
function double(x: Number) -> Number:
    return x * 2
''', encoding="utf-8")
    (tmp_path / "main.sl").write_text('''module demo
import math as first
import math as second
let a = first.double(3)
let b = second.double(4)
show a
show b
''', encoding="utf-8")

    program = parse_file(tmp_path / "main.sl")
    run(program)
    assert [show_expr_value(program, item) for item in program.show_exprs] == ["6", "8"]


def test_transitive_reexport_does_not_expose_private_symbol(tmp_path):
    (tmp_path / "base.sl").write_text('''module base
export visible
function visible() -> Number:
    return 1
function secret() -> Number:
    return 2
''', encoding="utf-8")
    (tmp_path / "middle.sl").write_text('''module middle
export visible from "base"
''', encoding="utf-8")
    (tmp_path / "api.sl").write_text('''module api
export secret from "middle"
''', encoding="utf-8")

    try:
        parse_file(tmp_path / "api.sl")
    except Exception as exc:
        assert "does not publicly export" in str(exc)
    else:
        raise AssertionError("private transitive symbol should not be re-exported")
