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


def test_effect_polymorphic_function_inherits_io_at_instantiation():
    result = pipeline('''
function apply<E>(f: Function<Text, Text, E>, x: Text) -> Text:
    return f(x)
function load(x: Text) -> Text:
    return read(x)
let values = ["a", "b"]
result = values |> map apply(load, item)
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert node.effects == ("io",)
    assert not node.parallel_safe


def test_effect_polymorphic_function_preserves_pure_instantiation():
    result = pipeline('''
function apply<E>(f: Function<Number, Number, E>, x: Number) -> Number:
    return f(x)
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3]
result = values |> map apply(double, item)
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert node.effects == ()
    assert node.parallel_safe


def test_pure_contract_rejects_effectful_function():
    source = '''
function only_pure(f: Function<Number, Number, pure>, x: Number) -> Number:
    return f(x)
function load(x: Number) -> Number:
    return to_number(read("x"))
result = only_pure(load, 1)
'''
    with pytest.raises(TypeError, match="expects Function<Number, Number, pure>"):
        p = parse(source)
        validate(p)


def test_effect_polymorphic_alias_instantiation():
    result = pipeline('''
function apply<E>(f: Function<Text, Text, E>, x: Text) -> Text:
    return f(x)
function load(x: Text) -> Text:
    return read(x)
let run = apply
let values = ["a", "b"]
result = values |> map run(load, item)
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert "io" in node.effects
    assert not node.parallel_safe
