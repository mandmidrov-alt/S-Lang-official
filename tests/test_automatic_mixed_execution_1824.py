from slang.core import parse, validate
from slang.runtime import execute
from slang.compiler_pipeline import compile_semantic_pipeline


def test_compiler_creates_reference_segment_from_real_backend_constraint():
    module = parse('''
function keep(x: Number) -> Boolean:
    return x > 1
data people:
    a age 1
    b age 2
    c age 3
older = people where keep(age)
mapped = older map age * 2
show mapped
''')
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast, backend_supported_strategies=("generic", "sequential-map", "effect:show"))
    modes = [segment.mode for segment in pipeline.selected_execution_plan.segments]
    assert modes == ["plan-runtime", "reference-interpreter", "plan-runtime"]
    fallback = pipeline.selected_execution_plan.segments[1]
    assert fallback.nodes == ("older#1",)
    choice = next(c for c in pipeline.strategies if c.node == "older#1")
    assert choice.strategy == "generic"
    assert not choice.runtime_supported


def test_runtime_executes_compiler_generated_mixed_segments():
    module = parse('''
function keep(x: Number) -> Boolean:
    return x > 1
data people:
    a age 1
    b age 2
    c age 3
older = people where keep(age)
mapped = older map age * 2
''')
    validate(module)
    result, executor = execute(module, backend_supported_strategies=("generic", "sequential-map"))
    assert executor.executor == "plan-runtime-segmented-bridge"
    assert result._collections["older"] == [{"name": "b", "age": 2}, {"name": "c", "age": 3}]
    assert result._collections["mapped"] == [4, 6]


def test_compiler_derives_segment_boundaries_from_dependency_graph():
    module = parse('''
function keep(x: Number) -> Boolean:
    return x > 1
data people:
    a age 1
    b age 2
    c age 3
older = people where keep(age)
mapped = older map age * 2
show mapped
''')
    validate(module)
    pipeline = compile_semantic_pipeline(
        module.ast,
        backend_supported_strategies=("generic", "sequential-map", "effect:show"),
    )
    segments = pipeline.selected_execution_plan.segments
    assert segments[0].entry_nodes == ("@fn:keep",)
    assert segments[0].exit_nodes == ("@fn:keep",)
    assert segments[1].entry_nodes == ("older#1",)
    assert segments[1].exit_nodes == ("older#1",)
    assert segments[2].entry_nodes == ("mapped#1",)
    assert segments[2].exit_nodes == ("@show:1#1",)


def test_runtime_dependency_validator_rejects_reversed_segments():
    from slang.selected_execution_plan import ExecutionSegment
    from slang.segment_bridge import validate_segment_dependencies

    module = parse("""
let a = 1
let b = a + 1
""")
    pipeline = compile_semantic_pipeline(module.ast)
    nodes = [step.node for step in pipeline.selected_execution_plan.steps]
    segments = (
        ExecutionSegment(0, "plan-runtime", (1,), (nodes[1],), ("generic",), (nodes[1],), (nodes[1],)),
        ExecutionSegment(1, "plan-runtime", (0,), (nodes[0],), ("generic",), (nodes[0],), (nodes[0],)),
    )
    try:
        validate_segment_dependencies(segments, pipeline.dependency_graph.edges)
    except ValueError as exc:
        assert "segment dependency order violation" in str(exc)
    else:
        raise AssertionError("dependency order violation was not rejected")
