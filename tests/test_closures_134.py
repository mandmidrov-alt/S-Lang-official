from slang.core import parse, validate, run


def run_program(src):
    p = parse(src)
    validate(p)
    run(p)
    return p


def test_nested_function_captures_outer_parameter():
    p = run_program('''
function make_multiplier(factor: Number) -> Function<Number, Number>:
    function multiply(x: Number) -> Number:
        return x * factor
    return multiply
let double = make_multiplier(2)
result = double(7)
''')
    assert p._bindings['result'] == 14


def test_closures_keep_independent_captured_values():
    p = run_program('''
function make_multiplier(factor: Number) -> Function<Number, Number>:
    function multiply(x: Number) -> Number:
        return x * factor
    return multiply
let double = make_multiplier(2)
let triple = make_multiplier(3)
a = double(4)
b = triple(4)
''')
    assert p._bindings['a'] == 8
    assert p._bindings['b'] == 12


def test_closure_can_capture_multiple_bindings():
    p = run_program('''
function make_shift(scale: Number, offset: Number) -> Function<Number, Number>:
    function transform(x: Number) -> Number:
        return x * scale + offset
    return transform
let f = make_shift(3, 2)
result = f(4)
''')
    assert p._bindings['result'] == 14


def test_nested_function_recursion_uses_lexical_binding():
    p = run_program('''
function make_sum_to() -> Function<Number, Number>:
    function sum_to(n: Number) -> Number:
        if n <= 0:
            return 0
        else:
            return n + sum_to(n - 1)
    return sum_to
let sum = make_sum_to()
result = sum(5)
''')
    assert p._bindings['result'] == 15


def test_nested_untyped_parameter_is_rejected():
    src = '''
function make() -> Function<Number, Number>:
    function inner(x) -> Number:
        return x
    return inner
'''
    try:
        validate(parse(src))
    except TypeError as exc:
        assert 'cannot infer parameter type for nested function' in str(exc)
    else:
        raise AssertionError('expected nested untyped parameter to be rejected')
