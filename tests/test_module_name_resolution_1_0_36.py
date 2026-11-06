from slang.core import parse_file, ParseError


def test_named_import_rejects_unknown_declaration(tmp_path):
    module = tmp_path / "math.sl"
    module.write_text('''module math
export double
function double(x: Number) -> Number:
    return x * 2
''', encoding="utf-8")
    main = tmp_path / "main.sl"
    main.write_text('''import math { triple }
''', encoding="utf-8")
    try:
        parse_file(main)
    except ParseError as exc:
        assert "does not export: triple" in str(exc)
    else:
        raise AssertionError("unknown named import should be rejected")


def test_import_alias_collision_is_rejected(tmp_path):
    for name in ("one", "two"):
        (tmp_path / f"{name}.sl").write_text(
            f'''module {name}\nexport value\nfunction value() -> Number:\n    return {1 if name == 'one' else 2}\n''',
            encoding="utf-8",
        )
    main = tmp_path / "main.sl"
    main.write_text('''import one as math
import two as math
''', encoding="utf-8")
    try:
        parse_file(main)
    except ParseError as exc:
        assert "duplicate imported namespace 'math'" in str(exc)
    else:
        raise AssertionError("duplicate import alias should be rejected")


def test_module_export_declaration_must_name_existing_symbol(tmp_path):
    module = tmp_path / "math.sl"
    module.write_text('''module math
export missing
function double(x: Number) -> Number:
    return x * 2
''', encoding="utf-8")
    main = tmp_path / "main.sl"
    main.write_text('''import math as m
''', encoding="utf-8")
    try:
        parse_file(main)
    except ParseError as exc:
        assert "exports unknown declaration(s): missing" in str(exc)
    else:
        raise AssertionError("unknown public export should be rejected")
