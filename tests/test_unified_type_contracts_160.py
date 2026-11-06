from slang.types import (
    NUMBER, TEXT, function_type, list_type, type_var,
    effect_contract_compatible, generic_match, substitute_type,
)


def test_nested_generic_function_type_unifies_type_and_effect_contract():
    expected = list_type(function_type((type_var('$T'),), type_var('$T'), ('$E',)))
    actual = list_type(function_type((NUMBER,), NUMBER, ('io',)))
    bindings = {}
    assert generic_match(expected, actual, bindings)
    assert bindings['$T'] == NUMBER
    assert bindings['$E'].name == 'EffectSet'
    assert 'io' in [a.name for a in bindings['$E'].args]


def test_substitution_reconstructs_nested_function_contract():
    expected = list_type(function_type((type_var('$T'),), TEXT, ('$E',)))
    bindings = {'$T': NUMBER, '$E': type('EffectSetValue', (), {})()}
    # Use the public effect-set representation rather than relying on an
    # internal marker object.
    from slang.types import effect_set_type
    bindings['$E'] = effect_set_type(('io',))
    resolved = substitute_type(expected, bindings)
    assert str(resolved) == 'List<Function<Number, Text, io>>'


def test_pure_contract_is_strict_but_effectful_contract_accepts_pure():
    pure = function_type((NUMBER,), NUMBER, ())
    io = function_type((NUMBER,), NUMBER, ('io',))
    assert effect_contract_compatible((), ())
    assert not effect_contract_compatible((), ('io',))
    assert effect_contract_compatible(('io',), ())
    assert effect_contract_compatible(('io',), ('io',))


def test_effect_variable_must_be_consistent_across_nested_positions():
    expected = function_type((function_type((TEXT,), TEXT, ('$E',)),), TEXT, ('$E',))
    same = function_type((function_type((TEXT,), TEXT, ('io',)),), TEXT, ('io',))
    different = function_type((function_type((TEXT,), TEXT, ('io',)),), TEXT, ('pure',))
    assert generic_match(expected, same, {})
    assert not generic_match(expected, different, {})


def test_unification_can_instantiate_actual_generic_variable():
    expected = list_type(NUMBER)
    actual = list_type(type_var('$T'))
    bindings = {}
    assert generic_match(expected, actual, bindings)
    assert bindings['$T'] == NUMBER
    assert substitute_type(actual, bindings) == expected


def test_compose_unifies_generic_function_result_with_outer_parameter():
    from slang.core import parse, validate
    p = parse('''
function identity<T>(x: T) -> T:
    return x
function double(x: Number) -> Number:
    return x * 2
let f = compose(double, identity)
''')
    validate(p)
    assert p.ast is not None


def test_generic_collection_return_is_substituted_recursively():
    from slang.core import parse, validate
    p = parse('''
function wrap<T>(x: T) -> List<T>:
    return [x]
let values = wrap(1)
''')
    validate(p)
    from slang.core import run
    run(p)
    assert p._bindings['values'] == [1]
