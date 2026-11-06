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


def test_closure_global_state_is_visible_to_memory_conflict_analysis():
    result = pipeline('''
state limit = 10
function above(x: Number) -> Boolean:
    return x > limit
let values = [1, 20, 30]
result = values |> map above
set limit = 20
''')
    node = next(n for n in result.optimized_ir.nodes if n.binding.startswith("result#"))
    write = next(n for n in result.optimized_ir.nodes if n.kind == "state:set")
    assert "limit" in node.memory_reads
    assert write.binding in node.dependencies or node.binding in write.dependencies


def test_pure_function_with_no_captured_state_keeps_parallel_map_safe():
    result = pipeline('''
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3, 4]
result = values |> map double
''')
    choice = next(c for c in result.strategies if c.node.startswith("result#"))
    assert "parallel-map" in choice.alternatives
    assert choice.strategy == "parallel-map"
