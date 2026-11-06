import pytest
from slang.core import parse_file, run, show_expr_value


def test_dotted_module_path_and_namespace(tmp_path):
    pkg = tmp_path / 'math' / 'basic'
    pkg.mkdir(parents=True)
    (pkg / 'core.sl').write_text('''module math.basic.core
export double
function double(x: Number) -> Number:
    return x * 2
''', encoding='utf-8')
    main = tmp_path / 'main.sl'
    main.write_text('''module demo
import math.basic.core as m
let value = m.double(6)
show value
''', encoding='utf-8')
    p = parse_file(main)
    run(p)
    assert [show_expr_value(p, x) for x in p.show_exprs] == ['12']


def test_reexport_builds_public_api(tmp_path):
    (tmp_path / 'base.sl').write_text('''module base
export double
function double(x: Number) -> Number:
    return x * 2
function hidden(x: Number) -> Number:
    return x * 9
''', encoding='utf-8')
    (tmp_path / 'api.sl').write_text('''module api
export double from "base"
''', encoding='utf-8')
    (tmp_path / 'main.sl').write_text('''module demo
import api { double }
let value = double(5)
show value
''', encoding='utf-8')
    p = parse_file(tmp_path / 'main.sl')
    run(p)
    assert [show_expr_value(p, x) for x in p.show_exprs] == ['10']
    api = parse_file(tmp_path / 'api.sl')
    assert api.ast.exports == ('double',)


def test_reexport_private_name_is_rejected(tmp_path):
    (tmp_path / 'base.sl').write_text('''module base
export public_fn
function public_fn(x: Number) -> Number:
    return x * 2
function hidden_fn(x: Number) -> Number:
    return x * 3
''', encoding='utf-8')
    (tmp_path / 'api.sl').write_text('''module api
export hidden_fn from "base"
''', encoding='utf-8')
    with pytest.raises(Exception, match='does not publicly export'):
        parse_file(tmp_path / 'api.sl')
