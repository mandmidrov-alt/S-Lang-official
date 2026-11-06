import pytest
from slang.core import parse, validate, run


def test_compose_unary_functions():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
function increment(x: Number) -> Number:
    return x + 1
let composed = compose(double, increment)
result = composed(4)
show result
''')
    validate(p); run(p)
    assert p._bindings['result'] == 10


def test_composition_can_be_chained():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
function increment(x: Number) -> Number:
    return x + 1
function negate(x: Number) -> Number:
    return 0 - x
let f = compose(double, increment)
let g = compose(negate, f)
result = g(4)
show result
''')
    validate(p); run(p)
    assert p._bindings['result'] == -10

def test_compose_type_mismatch_rejected():
    p = parse('''
function as_text(x: Number) -> Text:
    return "x"
function double(x: Number) -> Number:
    return x * 2
result = compose(double, as_text)
''')
    with pytest.raises(TypeError, match='compose type mismatch'):
        validate(p)


def test_compose_requires_unary_functions():
    p = parse('''
function add(a: Number, b: Number) -> Number:
    return a + b
function double(x: Number) -> Number:
    return x * 2
result = compose(add, double)
''')
    with pytest.raises(TypeError, match='unary functions'):
        validate(p)


def test_composed_function_can_be_applied():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
function increment(x: Number) -> Number:
    return x + 1
let f = compose(increment, double)
result = apply(f, 5)
show result
''')
    validate(p); run(p)
    assert p._bindings['result'] == 11


def test_composition_is_deterministic():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
function increment(x: Number) -> Number:
    return x + 1
let f = compose(double, increment)
let a = f(2)
let b = f(2)
show a
show b
''')
    validate(p); run(p)
    assert p._bindings['a'] == 6
    assert p._bindings['b'] == 6
