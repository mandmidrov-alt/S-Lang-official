from pathlib import Path
from slang.core import parse_file, run, show_expr_value


def test_namespace_and_selective_imports(tmp_path, capsys):
    (tmp_path / 'geometry.sl').write_text('''module geometry
export Circle, circumference

entity Circle:
    radius: m

function circumference(radius: m) -> m:
    return radius * 2

property Circle.diameter -> m:
    return self.radius * 2
''', encoding='utf-8')
    (tmp_path / 'main.sl').write_text('''module demo
import "geometry.sl" as geo

let disk = geo.Circle(10 m)
let c = geo.circumference(10 m)
show disk.diameter
show c
''', encoding='utf-8')
    p = parse_file(tmp_path / 'main.sl')
    run(p)
    assert [show_expr_value(p, x) for x in p.show_exprs] == ['20 m', '20 m']


def test_selective_import_hides_unselected_declaration(tmp_path):
    (tmp_path / 'mod.sl').write_text('''module mod
export public_fn

function public_fn(x: Number) -> Number:
    return x * 2

function hidden_fn(x: Number) -> Number:
    return x * 3
''', encoding='utf-8')
    (tmp_path / 'main.sl').write_text('''module demo
import "mod.sl" { public_fn }
let x = public_fn(4)
show x
''', encoding='utf-8')
    p = parse_file(tmp_path / 'main.sl')
    run(p)


def test_private_export_is_rejected(tmp_path):
    (tmp_path / 'mod.sl').write_text('''module mod
export public_fn
function public_fn(x: Number) -> Number:
    return x * 2
function hidden_fn(x: Number) -> Number:
    return x * 3
''', encoding='utf-8')
    (tmp_path / 'main.sl').write_text('''module demo
import "mod.sl" { hidden_fn }
''', encoding='utf-8')
    import pytest
    with pytest.raises(Exception, match='does not publicly export'):
        parse_file(tmp_path / 'main.sl')
