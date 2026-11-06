from dataclasses import replace

from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.selected_execution_plan import build_selected_execution_plan


def compile_source(source):
    module = parse(source)
    validate(module)
    return compile_semantic_pipeline(module.ast)


def test_selected_plan_has_explicit_plan_runtime_segments():
    result = compile_source('''
function identity(x: Number) -> Number:
    return x

let seed = 1

data people:
    a age 1
    b age 2
    c age 3
older = people where age > 1
show older
''')
    plan = result.selected_execution_plan
    assert plan.segments
    assert all(segment.mode == "plan-runtime" for segment in plan.segments)
    assert tuple(n for segment in plan.segments for n in segment.nodes) == tuple(step.node for step in plan.steps)


def test_selected_plan_partitions_runtime_and_reference_regions():
    result = compile_source('''
function identity(x: Number) -> Number:
    return x

let seed = 1

data people:
    a age 1
    b age 2
    c age 3
older = people where age > 1
show older
''')
    kinds = {n.binding: n.kind for n in result.optimized_ir.nodes}
    choices = tuple(
        replace(choice, strategy="generic", runtime_supported=False)
        if choice.node == "older#1" else choice
        for choice in result.strategies
    )
    # `generic` is intentionally illegal for filter in the runtime contract;
    # this simulates a backend/strategy artifact that requires fallback.
    selected = build_selected_execution_plan(
        result.execution_plan,
        choices,
        result.execution_profile,
        node_kinds=kinds,
    )
    assert [segment.mode for segment in selected.segments] == ["reference-interpreter", "plan-runtime"]
    assert selected.segments[0].nodes == ("older#1",)
    assert selected.segments[1].entry_nodes == ("seed#1",)
    assert selected.segments[0].exit_nodes == ("older#1",)


def test_segmentation_is_deterministic():
    a = compile_source('''
function identity(x: Number) -> Number:
    return x

let seed = 1

data people:
    a age 1
    b age 2
    c age 3
older = people where age > 1
mapped = older map age * 2
show mapped
''').selected_execution_plan
    b = compile_source('''
function identity(x: Number) -> Number:
    return x

let seed = 1

data people:
    a age 1
    b age 2
    c age 3
older = people where age > 1
mapped = older map age * 2
show mapped
''').selected_execution_plan
    assert a.segments == b.segments
