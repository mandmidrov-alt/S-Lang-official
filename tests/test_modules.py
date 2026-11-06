import sys
from pathlib import Path
sys.path.insert(0, '.')
from slang.core import parse_file, validate, run, show_expr_value, ParseError


def test_source_module_import(tmp_path):
    lib = tmp_path / "geometry.sl"
    lib.write_text('''module geometry\n\nentity Circle:\n    radius: m\n\nproperty Circle.diameter -> m:\n    return self.radius * 2\n''', encoding='utf-8')
    main = tmp_path / "main.sl"
    main.write_text('''module demo\nimport "geometry.sl"\n\nlet disk = Circle(10 m)\nshow disk.radius, disk.diameter\n''', encoding='utf-8')
    p = parse_file(main)
    validate(p); run(p)
    assert [show_expr_value(p, x) for x in p.show_exprs] == ['10 m', '20 m']


def test_nested_module_import(tmp_path):
    leaf = tmp_path / "leaf.sl"
    leaf.write_text('entity Meter:\n    value: m\n', encoding='utf-8')
    mid = tmp_path / "mid.sl"
    mid.write_text('import "leaf.sl"\nproperty Meter.double -> m:\n    return self.value * 2\n', encoding='utf-8')
    main = tmp_path / "main.sl"
    main.write_text('import "mid.sl"\nlet x = Meter(3 m)\nshow x.double\n', encoding='utf-8')
    p = parse_file(main); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '6 m'


def test_missing_module_is_reported(tmp_path):
    main = tmp_path / "main.sl"
    main.write_text('import "missing.sl"\n', encoding='utf-8')
    try:
        parse_file(main)
    except ParseError as e:
        assert "import not found" in str(e)
        return
    assert False


def test_cyclic_import_is_reported(tmp_path):
    a = tmp_path / "a.sl"; b = tmp_path / "b.sl"
    a.write_text('import "b.sl"\n', encoding='utf-8')
    b.write_text('import "a.sl"\n', encoding='utf-8')
    try:
        parse_file(a)
    except ParseError as e:
        assert "cyclic import" in str(e)
        return
    assert False
