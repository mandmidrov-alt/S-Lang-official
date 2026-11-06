from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.selected_execution_plan import format_selected_execution_plan


def _source():
    return '''
record Person:
    name: Text
    age: Number
record R1:
    label: Text
    value: Number
record R2:
    label: Text
    value: Number
record R3:
    label: Text
    value: Number
let people = [Person("A", 20), Person("B", 30)]
a = people map R1(row.name, row.age + 1)
b = a map R2(row.label, row.value + 2)
c = b map R3(row.label, row.value + 3)
show c
'''


def test_selected_plan_contains_authoritative_record_plan():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    selected = pipeline.selected_execution_plan
    assert selected.record_plan is pipeline.global_plan_cost.record_plan
    assert selected.record_plan is not None
    assert selected.record_plan.mode in {'full', 'partial', 'materialized'}
    assert selected.record_plan.fused_segments


def test_selected_plan_format_reports_record_boundaries():
    module = parse(_source())
    validate(module)
    selected = compile_semantic_pipeline(module.ast).selected_execution_plan
    rendered = format_selected_execution_plan(selected)
    assert 'record_plan =' in rendered
    assert 'segments =' in rendered
