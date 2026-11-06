from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.runtime import execute, _segment_execution_mode

SOURCE = """function double(x: Number) -> Number:
    return x * 2

let values = [1, 2, 3]
result = values |> map double
show result
"""

def test_segmented_runtime_executes_supported_plan():
    module = parse(SOURCE)
    validate(module)
    _, trace = execute(module)
    pipeline = compile_semantic_pipeline(module.ast)
    assert pipeline.selected_execution_plan.segments
    assert all(s.mode == "plan-runtime" for s in pipeline.selected_execution_plan.segments)
    assert trace.executor == "plan-runtime-segmented"
    assert trace.completed == trace.operation_count

def test_segment_coverage_matches_selected_plan():
    module = parse(SOURCE)
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    segments = _segment_execution_mode(pipeline)
    assert tuple(n for s in segments for n in s.nodes) == tuple(x.node for x in pipeline.selected_execution_plan.steps)
    assert [s.index for s in segments] == list(range(len(segments)))
