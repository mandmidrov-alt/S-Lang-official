from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.function_effects import analyze_function_effects


def effects(source):
    p = parse(source)
    validate(p)
    return {s.function: s for s in analyze_function_effects(p.ast)}


def test_pure_function_is_pure():
    got = effects('''
function double(x: Number) -> Number:
    return x * 2
''')
    assert got['double'].effects == ()
    assert got['double'].parallel_safe


def test_function_call_effects_propagate():
    got = effects('''
function clean(x: Number) -> Number:
    return x * 2
function outer(x: Number) -> Number:
    return clean(x) + 1
''')
    assert got['outer'].effects == ()
    assert got['outer'].calls == ('clean',)


def test_state_read_is_reported():
    got = effects('''
state limit = 10
function above(x: Number) -> Boolean:
    return x > limit
''')
    assert got['above'].effects == ('state-read',)
    assert got['above'].parallel_safe
    assert not got['above'].order_sensitive


def test_io_call_propagates_to_caller():
    got = effects('''
function load(path: Text) -> List<Record>:
    return read_csv(path)
function use(path: Text) -> List<Record>:
    return load(path)
''')
    assert got['load'].effects == ('io',)
    assert got['use'].effects == ('io',)
    assert not got['use'].parallel_safe


def test_compiler_pipeline_exposes_function_contracts():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
let result = double(4)
''')
    validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    assert [s.function for s in pipeline.function_effects] == ['double']
    assert pipeline.function_effects[0].effects == ()
