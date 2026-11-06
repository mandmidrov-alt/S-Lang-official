from pathlib import Path
from slang.core import parse, validate, run

def _program(source):
    return parse(source, base_dir=Path('.'))

def test_generic_record_field_can_flow_directly_into_generic_call():
    p = _program('''
record Box<T>:
    value: T
let result = first(Box([1, 2, 3]).value)
''')
    validate(p)
    run(p)
    assert p._bindings['result'] == 1

def test_nested_generic_record_collection_chain():
    p = _program('''
record Box<T>:
    value: T
let result = first(flatten(Box([[1, 2], [3, 4]]).value))
''')
    validate(p)
    run(p)
    assert p._bindings['result'] == 1

def test_generic_record_field_preserves_text_type():
    p = _program('''
record Box<T>:
    value: T
let result = first(Box(["a", "b"]).value)
''')
    validate(p)
    run(p)
    assert p._bindings['result'] == 'a'

def test_generic_record_field_can_feed_user_function():
    p = _program('''
record Box<T>:
    value: T
function first_number(values: List<Number>) -> Number:
    return first(values)
let result = first_number(Box([10, 20, 30]).value)
''')
    validate(p)
    run(p)
    assert p._bindings['result'] == 10

def test_nonmatching_generic_record_field_is_rejected():
    p = _program('''
record Box<T>:
    value: T
function need_numbers(values: List<Number>) -> Number:
    return first(values)
let result = need_numbers(Box(["a", "b"]).value)
''')
    try:
        validate(p)
    except TypeError as exc:
        assert 'need_numbers' in str(exc)
    else:
        raise AssertionError('expected incompatible generic record field type')
