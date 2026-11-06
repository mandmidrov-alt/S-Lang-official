import pytest

from slang.core import parse, validate
from slang.types import BOOLEAN, NUMBER, function_type, list_type, type_var, unify_types


def test_return_only_generic_function_is_rejected_as_uninferable():
    p = parse('''
function make<T>() -> List<T>:
    return []
''')
    with pytest.raises(TypeError, match="cannot be inferred from arguments: T"):
        validate(p)


def test_sequence_and_state_checks_use_recursive_unification():
    p = parse('''
state value = 1
set value = 2
sequence values from 1 for 3 steps using value + 1
''')
    validate(p)


def test_nested_function_contract_is_checked_recursively():
    expected = function_type((list_type(type_var('$T')),), list_type(type_var('$T')))
    actual = function_type((list_type(NUMBER),), list_type(NUMBER))
    bindings = {}
    assert unify_types(expected, actual, bindings)
    assert bindings['$T'] == NUMBER


def test_generic_branch_contract_conflict_is_rejected():
    p = parse('''
function first<T>(x: T) -> T:
    return x
let result = if true then first(1) else "text"
''')
    with pytest.raises(TypeError):
        validate(p)


def test_function_effect_contract_survives_unified_declared_return():
    p = parse('''
function load(x: Text) -> Text:
    return read(x)
function lift<E>(f: Function<Text, Text, E>) -> Function<Text, Text, E>:
    return f
function make() -> Function<Text, Text>:
    return lift(load)
''')
    validate(p)
