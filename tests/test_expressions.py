from pathlib import Path
import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value

def test_generic_expression_ast_and_evaluation():
    p=parse(Path('examples/expression.sl').read_text()); validate(p); run(p)
    values=[show_expr_value(p,e) for e in p.show_exprs]
    assert values[0] == '149600000000 m'
    assert values[1] == '314.159265358979 m2'
    assert values[2] == '100 m2'

def test_unknown_function_rejected():
    p=parse('body a:\n    mass 1 kg\n    position 0 m\n    velocity 0 mps\nshow foo(a)\n')
    try: validate(p)
    except TypeError as e:
        assert "unknown function 'foo'" in str(e); return
    assert False

def test_incompatible_expression_units_rejected():
    p=parse('circle disk:\n    radius 10 m\nshow disk.radius + 2 kg\n')
    try: validate(p)
    except TypeError: return
    assert False
