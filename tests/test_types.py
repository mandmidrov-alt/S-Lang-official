import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, Quantity, UNIT_DIM
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER, BOOLEAN, quantity_type
from slang.ast import Binary, Literal, Compare, Field, Name, Property


def test_quantity_type_algebra():
    env = TypeEnv(names={}, fields={}, properties={})
    assert infer(Binary('*', Literal(2), Literal(3)), env) == NUMBER
    m = quantity_type(UNIT_DIM['m'])
    s = quantity_type(UNIT_DIM['s'])
    assert infer(Binary('/', Literal(Quantity(10,'m')), Literal(Quantity(2,'s'))), env).dimension == (0,1,-1)
    assert infer(Compare('>=', Literal(2), Literal(1)), env) == BOOLEAN


def test_data_filter_and_sort_use_generic_type_inference():
    src = open('examples/data_generic.sl').read()
    p = parse(src)
    validate(p)
    expr = p.ast.filters[0].predicate.expr
    env = TypeEnv(names={'row': __import__('slang.types', fromlist=['Type']).Type('Row')}, fields={'Row': {'age': NUMBER, 'score': NUMBER}}, properties={})
    assert infer(expr, env) == BOOLEAN
    assert infer(p.ast.sorts[0].spec.expr, env) == NUMBER


def test_invalid_unit_comparison_is_rejected_by_generic_layer():
    src = '''physics gravity\n\nbody sun:\n    mass 1 kg\n    position 0 m\n    velocity 0 mps\n\nbody earth:\n    mass 1 kg\n    position 1 m\n    velocity 1 mps\n\nsimulate earth around sun for 1 second step 1 second\n'''
    p = parse(src)
    # The existing parser does not expose arbitrary body expressions yet;
    # direct semantic inference still verifies incompatible dimensions.
    env = TypeEnv(names={}, fields={}, properties={})
    try:
        infer(Compare('>=', Literal(Quantity(1,'m')), Literal(Quantity(1,'kg'))), env)
    except TypeError:
        return
    assert False
