from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


def _source():
    return """
record Person:
    id: Number
    name: Text
    score: Number
record R1:
    id: Number
    label: Text
    value: Number
let people = [Person(1, \"A\", 5), Person(2, \"B\", 7)]
r1 = people map R1(row.id, row.name, row.score + 1)
r2 = r1 map R1(row.id, row.label, row.value + 2)
selected = r1 where row.id > 0
show selected
"""


def test_selected_record_plan_carries_field_strategies():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    plan = pipeline.selected_execution_plan.record_plan
    assert plan is not None
    assert plan.field_strategies
    assert any(row[0] == 'r1' and row[2] == 'value' for row in plan.field_strategies)
    assert tuple(plan.field_strategies) == tuple(pipeline.global_plan_cost.record_field_strategies)


def test_backend_consumes_selected_record_field_plan():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'record_field_plan = ' in text
    assert 'value:recompute:' in text
    assert 'id:full:' in text
