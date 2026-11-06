from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_profile import ExecutionProfile
from slang.function_effects import analyze_function_effects


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


def test_generic_factory_preserves_returned_function_effect():
    source = '''
function lift<E>(f: Function<Text, Text, E>) -> Function<Text, Text, E>:
    return f
function load(x: Text) -> Text:
    return read(x)
let lifted = lift(load)
let values = ["a", "b"]
result = values |> map lifted(item)
'''
    result = pipeline(source)
    higher = next(x for x in result.higher_order_effects if x.operation == "map")
    assert higher.effects == ("io",)
    assert not higher.parallel_safe
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert node.effects == ("io",)
    assert not node.parallel_safe


def test_generic_factory_preserves_pure_returned_function_effect():
    source = '''
function lift<E>(f: Function<Number, Number, E>) -> Function<Number, Number, E>:
    return f
function double(x: Number) -> Number:
    return x * 2
let lifted = lift(double)
let values = [1, 2, 3]
result = values |> map lifted(item)
'''
    result = pipeline(source)
    higher = next(x for x in result.higher_order_effects if x.operation == "map")
    assert higher.effects == ()
    assert higher.parallel_safe


def test_generic_factory_contract_is_deterministic():
    source = '''
function lift<E>(f: Function<Text, Text, E>) -> Function<Text, Text, E>:
    return f
function load(x: Text) -> Text:
    return read(x)
let lifted = lift(load)
let values = ["a"]
result = values |> map lifted(item)
'''
    a = pipeline(source).higher_order_effects
    b = pipeline(source).higher_order_effects
    assert a == b


def test_function_effect_summary_exposes_polymorphic_return_contract():
    source = '''
function lift<E>(f: Function<Text, Text, E>) -> Function<Text, Text, E>:
    return f
'''
    summary = analyze_function_effects(parse(source).ast)[0]
    assert summary.returned_function_effects == ("$E",)
