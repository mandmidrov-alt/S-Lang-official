from slang.types import NUMBER, TEXT, function_type, list_type, type_var, generic_match, substitute_type

def test_nested_function_collection_unifies():
    expected = list_type(function_type((type_var('$T'),), type_var('$T'), ('$E',)))
    actual = list_type(function_type((NUMBER,), NUMBER, ('io',)))
    bindings = {}
    assert generic_match(expected, actual, bindings)
    assert substitute_type(expected, bindings) == actual

def test_conflicting_nested_function_types_reject():
    expected = list_type(function_type((type_var('$T'),), type_var('$T'), ('$E',)))
    actual = list_type(function_type((TEXT,), NUMBER, ('io',)))
    assert not generic_match(expected, actual, {})

def test_nested_actual_variables_are_instantiated():
    expected = function_type((list_type(NUMBER),), list_type(TEXT), ('io',))
    actual = function_type((list_type(type_var('$T')),), list_type(type_var('$U')), ('io',))
    bindings = {}
    assert generic_match(expected, actual, bindings)
    assert bindings['$T'] == NUMBER
    assert bindings['$U'] == TEXT
    assert substitute_type(actual, bindings) == expected

def test_repeated_nested_variable_remains_consistent():
    expected = function_type((list_type(type_var('$T')),), type_var('$T'), ('$E',))
    actual = function_type((list_type(NUMBER),), TEXT, ('io',))
    assert not generic_match(expected, actual, {})

def test_conditional_generic_branches_use_unified_substitution():
    from slang.core import parse, validate
    p = parse('''
function identity<T>(x: T) -> T:
    return x
function number(x: Number) -> Number:
    return x
let f = if true then identity else number
''')
    validate(p)
    from slang.semantic import TypeEnv, infer
    ftype = infer(p.ast.bindings[-1].expr, TypeEnv({}, {}, {}, {'identity': ((type_var('$T'),), type_var('$T')), 'number': ((NUMBER,), NUMBER)}, {}, {}))
    assert str(ftype) == 'Function<Number, Number>'
