import pytest
from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_profile import ExecutionProfile


def pipeline(source):
    p = parse(source)
    validate(p)
    return compile_semantic_pipeline(
        p.ast,
        backend_parallelism=("sequential", "parallel-where-independent"),
        backend_memory_models=("abstract", "linear-buffer"),
        backend_orderings=("source-order", "dependency-ordered"),
        execution_profile=ExecutionProfile(cpu_cores=4, allow_parallelism=True),
    )


def test_two_level_alias_in_map_inherits_io_effect():
    result = pipeline('''
function load(path: Text) -> Text:
    return read(path)
let first = load
let second = first
let paths = ["a", "b"]
result = paths |> map second
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert "io" in node.effects
    assert not node.parallel_safe


def test_compose_in_map_unions_function_effects():
    result = pipeline('''
function load(path: Text) -> Text:
    return read(path)
function identity(x: Text) -> Text:
    return x
let transform = compose(identity, load)
let paths = ["a", "b"]
result = paths |> map transform
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert "io" in node.effects
    assert not node.parallel_safe


def test_apply_alias_in_function_body_propagates_effect():
    result = pipeline('''
function load(path: Text) -> Text:
    return read(path)
function run(x: Text) -> Text:
    return apply(load, x)
let paths = ["a", "b"]
result = paths |> map run
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert "io" in node.effects
    assert not node.parallel_safe


def test_pure_higher_order_chain_remains_parallel_safe():
    result = pipeline('''
function double(x: Number) -> Number:
    return x * 2
function identity(x: Number) -> Number:
    return x
let a = double
let b = a
let transform = compose(identity, b)
let values = [1, 2, 3, 4]
result = values |> map transform
''')
    choice = next(c for c in result.strategies if c.node.startswith("result#"))
    assert "parallel-map" in choice.alternatives


def test_function_effect_analysis_resolves_local_alias_chain():
    from slang.function_effects import analyze_function_effects
    p = parse('''
function load(path: Text) -> Text:
    return read(path)
function wrapper(path: Text) -> Text:
    let a = load
    let b = a
    return b(path)
''')
    validate(p)
    summary = {s.function: s for s in analyze_function_effects(p.ast)}["wrapper"]
    assert summary.effects == ("io",)
    assert not summary.parallel_safe
