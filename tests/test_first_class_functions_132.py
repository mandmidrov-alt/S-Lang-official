from slang.core import parse, validate, run


def test_function_reference_and_apply():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
let f = double
result = apply(f, 5)
show result
''')
    validate(p)
    run(p)
    assert p._bindings['result'] == 10


def test_map_accepts_function_reference():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3]
result = values |> map double
show result
''')
    validate(p)
    run(p)
    assert p._collections['result'] == [2, 4, 6]


def test_where_accepts_boolean_function_reference():
    p = parse('''
function positive(x: Number) -> Boolean:
    return x > 0
let values = [0, 2, 3]
result = values |> where positive
show result
''')
    validate(p)
    run(p)
    assert p._collections['result'] == [2, 3]


def test_wrong_function_result_is_rejected_for_where():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
data values:
    a value 1
result = values |> where double
''')
    try:
        validate(p)
    except TypeError as exc:
        assert 'where function must return Boolean' in str(exc)
    else:
        raise AssertionError('expected type error')


def test_function_type_flows_through_local_binding():
    p = parse('''
function triple(x: Number) -> Number:
    return x * 3
function use(f, x: Number) -> Number:
    return apply(f, x)
let f = triple
result = use(f, 4)
show result
''')
    validate(p)
    run(p)
    assert p._bindings['result'] == 12
