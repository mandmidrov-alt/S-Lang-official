from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.runtime import build_runtime_trace, validate_runtime_plan, execute


def source():
    return '''
let people = [{name: "A", team: "X", score: 1}, {name: "B", team: "X", score: 2}]
let groups = group_count(people, "team")
let totals = group_sum(people, "team", "score")
'''


def test_runtime_plan_is_complete_and_trace_is_deterministic():
    p = parse(source())
    validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    validate_runtime_plan(pipeline)
    trace = build_runtime_trace(pipeline)
    assert trace.deterministic
    assert trace.operation_count == len(pipeline.selected_execution_plan.steps)
    assert trace.completed == trace.operation_count


def test_runtime_execute_preserves_reference_semantics():
    p = parse(source())
    validate(p)
    module, trace = execute(p)
    assert module._collections["groups"] == [{"key": "X", "count": 2}]
    assert module._collections["totals"] == [{"key": "X", "sum": 3}]
    assert trace.completed == trace.operation_count
