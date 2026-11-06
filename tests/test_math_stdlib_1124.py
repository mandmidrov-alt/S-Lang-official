import math

from slang.core import parse, parse_expr, run, validate
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER


def execute(source):
    program = parse(source)
    validate(program)
    run(program)
    return program._bindings


def test_hyperbolic_signatures_and_runtime():
    env = TypeEnv({}, {}, {})
    for source in (
        'sinh_number(0)', 'cosh_number(0)', 'tanh_number(0)',
        'asinh_number(0)', 'acosh_number(1)', 'atanh_number(0)',
    ):
        assert infer(parse_expr(source), env) == NUMBER
    values = execute('''
a = sinh_number(0)
b = cosh_number(0)
c = tanh_number(0)
d = asinh_number(0)
e = acosh_number(1)
f = atanh_number(0)
''')
    assert values == {'a': 0, 'b': 1, 'c': 0, 'd': 0, 'e': 0, 'f': 0}


def test_hyperbolic_values_match_python_math():
    values = execute('''
a = sinh_number(1)
b = cosh_number(1)
c = tanh_number(1)
d = asinh_number(1)
e = acosh_number(2)
f = atanh_number(0.5)
''')
    assert math.isclose(values['a'], math.sinh(1))
    assert math.isclose(values['b'], math.cosh(1))
    assert math.isclose(values['c'], math.tanh(1))
    assert math.isclose(values['d'], math.asinh(1))
    assert math.isclose(values['e'], math.acosh(2))
    assert math.isclose(values['f'], math.atanh(0.5))


def test_inverse_hyperbolic_domain_validation():
    for source in ('acosh_number(0)', 'atanh_number(1)', 'atanh_number(0 - 1)'):
        try:
            execute(f'x = {source}\n')
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError(f'expected validation/runtime failure for {source}')
