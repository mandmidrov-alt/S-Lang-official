from slang.core import parse
from slang.function_effects import analyze_function_effects


def summaries(source):
    p = parse(source)
    return {s.function: s for s in analyze_function_effects(p.ast)}


def test_pure_captured_value_is_reported_without_effect():
    got = summaries('''
function make(factor: Number) -> Function<Number, Number>:
    function multiply(x: Number) -> Number:
        return x * factor
    return multiply
''')
    assert got['make'].effects == ()
    nested = got['make.multiply']
    assert nested.captures == ('factor',)
    assert nested.parallel_safe


def test_captured_global_state_enters_closure_effect_contract():
    got = summaries('''
state limit = 10
function make() -> Function<Number, Number>:
    function above(x: Number) -> Number:
        return x + limit
    return above
''')
    nested = got['make.above']
    assert nested.effects == ('state-read',)
    assert nested.parallel_safe
    assert got['make'].effects == ()
    assert got['make'].returned_function_effects == ('state-read',)


def test_io_closure_does_not_make_factory_itself_effectful():
    got = summaries('''
function make_loader() -> Function<Text, Text>:
    function load(path: Text) -> Text:
        return read(path)
    return load
''')
    assert got['make_loader'].effects == ()
    assert got['make_loader'].parallel_safe
    assert got['make_loader.load'].effects == ('io',)
    assert not got['make_loader.load'].parallel_safe
    assert got['make_loader'].returned_function_effects == ('io',)


def test_nested_call_propagates_closure_effect_to_caller():
    got = summaries('''
function outer() -> Number:
    function load(x: Text) -> Text:
        return read(x)
    function use(x: Text) -> Text:
        return load(x)
    return 1
''')
    assert got['outer.load'].effects == ('io',)
    assert got['outer.use'].effects == ('io',)
    assert not got['outer.use'].parallel_safe
    assert got['outer'].effects == ()
