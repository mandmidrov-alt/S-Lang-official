from slang.core import parse_file, validate, run


def test_function_value_can_be_called_directly(tmp_path):
    src = '''
function double(x: Number) -> Number:
    return x * 2
let transform = double
result = transform(5)
show result
'''
    path = tmp_path / 'direct_call.sl'
    path.write_text(src)
    validate(parse_file(str(path)))
    p = run(parse_file(str(path)))
    assert p._bindings['result'] == 10


def test_local_function_value_can_be_called_inside_function(tmp_path):
    src = '''
function double(x: Number) -> Number:
    return x * 2
function apply_twice(f, x: Number) -> Number:
    return f(f(x))
result = apply_twice(double, 3)
show result
'''
    path = tmp_path / 'nested_call.sl'
    path.write_text(src)
    validate(parse_file(str(path)))
    p = run(parse_file(str(path)))
    assert p._bindings['result'] == 12


def test_non_function_binding_is_rejected_as_callable(tmp_path):
    src = '''
let value = 5
result = value(2)
'''
    path = tmp_path / 'bad_call.sl'
    path.write_text(src)
    try:
        validate(parse_file(str(path)))
    except TypeError as exc:
        assert 'unknown function' in str(exc) or 'Function' in str(exc)
    else:
        raise AssertionError('expected callable type error')


def test_named_function_still_calls_normally(tmp_path):
    src = '''
function double(x: Number) -> Number:
    return x * 2
result = double(7)
show result
'''
    path = tmp_path / 'named_call.sl'
    path.write_text(src)
    validate(parse_file(str(path)))
    p = run(parse_file(str(path)))
    assert p._bindings['result'] == 14
