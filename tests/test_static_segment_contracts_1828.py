from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.selected_execution_plan import format_selected_execution_plan


def test_compiler_embeds_contracts_in_selected_execution_plan():
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
    assert all(segment.data_contract is not None for segment in segments)
    fallback = next(segment for segment in segments if segment.mode == "reference-interpreter")
    assert fallback.data_contract.inputs == ("@fn:keep",)
    assert fallback.data_contract.outputs == ("older",)
    plan_segment = next(segment for segment in segments if "mapped#1" in segment.nodes)
    assert plan_segment.data_contract.inputs == ("older",)
    assert plan_segment.data_contract.outputs == ("mapped",)


def test_selected_plan_format_exposes_boundary_contracts():
    module = parse('''
function keep(x: Number) -> Boolean:
    return x > 1

data people:
    a age 1
    b age 2
older = people where keep(age)
mapped = older map age * 2
''')
    validate(module)
    pipeline = compile_semantic_pipeline(
        module.ast,
        backend_supported_strategies=("generic", "sequential-map"),
    )
    rendered = format_selected_execution_plan(pipeline.selected_execution_plan)
    assert "contract =" in rendered
    assert "outputs:older" in rendered
    assert "inputs:older" in rendered
