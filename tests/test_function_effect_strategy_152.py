from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_profile import ExecutionProfile


def pipeline(source):
    p = parse(source)
    validate(p)
    return compile_semantic_pipeline(p.ast, backend_parallelism=("sequential", "parallel-where-independent"), backend_memory_models=("abstract", "linear-buffer"), backend_orderings=("source-order", "dependency-ordered"), execution_profile=ExecutionProfile(cpu_cores=4, allow_parallelism=True))


def test_pure_function_keeps_parallel_map_eligible():
    result = pipeline(
        """
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3, 4]
result = values |> map double
"""
    )
    choice = next(c for c in result.strategies if c.node.startswith("result#"))
    assert "parallel-map" in choice.alternatives


def test_io_function_blocks_parallel_map():
    result = pipeline(
        """
function load(path: Text) -> Text:
    return read(path)
let paths = ["a", "b", "c"]
result = paths |> map load
"""
    )
    choice = next(c for c in result.strategies if c.node.startswith("result#"))
    assert choice.strategy != "parallel-map"
    assert all(name != "parallel-map" for name, _ in choice.scores)


def test_state_read_function_remains_parallel_safe():
    result = pipeline(
        """
state limit = 10
function above(x: Number) -> Boolean:
    return x > limit
let values = [1, 20, 30]
result = values |> map above
"""
    )
    choice = next(c for c in result.strategies if c.node.startswith("result#"))
    assert "parallel-map" in choice.alternatives


def test_function_effects_reach_execution_ir():
    result = pipeline(
        """
function load(path: Text) -> Text:
    return read(path)
let paths = ["a", "b"]
result = paths |> map load
"""
    )
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    assert "io" in node.effects
    assert not node.parallel_safe
