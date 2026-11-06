from slang.core import parse, validate, run


def test_generic_record_constructor_and_field_inference():
    p = parse('''
record Box<T>:
    value: T

function unwrap(box: Box<Number>) -> Number:
    return box.value

let b = Box(42)
let x = unwrap(b)
''')
    validate(p)
    run(p)
    assert p._bindings['b'].type_name == 'Box'
    assert p._bindings['b']['value'] == 42
    assert p._bindings['x'] == 42


def test_generic_record_field_preserves_text_type():
    p = parse('''
record Box<T>:
    value: T

function unwrap(box: Box<Text>) -> Text:
    return box.value

let b = Box("hello")
let x = unwrap(b)
''')
    validate(p)
    run(p)
    assert p._bindings['x'] == 'hello'


def test_generic_record_nested_collection_field():
    p = parse('''
record Box<T>:
    value: T

function first_value(box: Box<List<Number>>) -> Number:
    return first(box.value)

let b = Box([1, 2, 3])
let x = first_value(b)
''')
    validate(p)
    run(p)
    assert p._bindings['x'] == 1


def test_generic_record_wrong_field_type_is_rejected():
    p = parse('''
record Box<T>:
    value: T

function need_number(box: Box<Number>) -> Number:
    return box.value

let b = Box("text")
let x = need_number(b)
''')
    try:
        validate(p)
    except TypeError:
        return
    raise AssertionError('expected incompatible generic record type to fail')
