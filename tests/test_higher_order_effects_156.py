import pytest
from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_profile import ExecutionProfile


def pipeline(source):
    p = parse(source); validate(p)
    return compile_semantic_pipeline(
        p.ast,
        backend_parallelism=("sequential", "parallel-where-independent"),
        backend_memory_models=("abstract", "linear-buffer"),
        backend_orderings=("source-order", "dependency-ordered"),
        execution_profile=ExecutionProfile(cpu_cores=4, allow_parallelism=True),
    )


def test_map_compose_propagates_io():
    r = pipeline('''
function load(x: Text) -> Text:
    return read(x)
function double_text(x: Text) -> Text:
    return x
let values = ["a", "b"]
result = values |> map compose(double_text, load)
''')
    h = next(x for x in r.higher_order_effects if x.operation == 'map')
    assert h.effects == ('io',)
    assert not h.parallel_safe


def test_where_alias_propagates_io():
    r = pipeline('''
function check(x: Text) -> Boolean:
    return exists(x)
let predicate = check
let values = ["a", "b"]
result = values |> where predicate
''')
    h = next(x for x in r.higher_order_effects if x.operation == 'where')
    assert h.effects == ('io',)
    assert not h.parallel_safe


def test_reduce_apply_propagates_effect():
    r = pipeline('''
function load(x: Text) -> Text:
    return read(x)
function step(acc: Text, item: Text) -> Text:
    return apply(load, item)
let values = ["a", "b"]
result = values |> reduce "" with step(acc, item)
''')
    h = next(x for x in r.higher_order_effects if x.operation == 'reduce')
    assert h.effects == ('io',)


def test_pure_higher_order_chain_remains_parallel_safe():
    r = pipeline('''
function double(x: Number) -> Number:
    return x * 2
function increment(x: Number) -> Number:
    return x + 1
let values = [1, 2, 3]
result = values |> map compose(double, increment)
''')
    h = next(x for x in r.higher_order_effects if x.operation == 'map')
    assert h.effects == ()
    assert h.parallel_safe


def test_higher_order_analysis_is_deterministic():
    source = '''
function load(x: Text) -> Text:
    return read(x)
let f = load
let values = ["a", "b"]
result = values |> map compose(f, f)
'''
    a = pipeline(source).higher_order_effects
    b = pipeline(source).higher_order_effects
    assert a == b
