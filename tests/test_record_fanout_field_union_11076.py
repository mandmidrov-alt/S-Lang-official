from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


def _source():
    return '''
record Person:
    id: Number
    name: Text
    age: Number
    unused: Number
record R:
    id: Number
    name: Text
    value: Number
    unused: Number
let people = [Person(1, "A", 20, 99), Person(2, "B", 30, 88)]
r1 = people map R(row.id, row.name, row.age + 1, row.unused)
r2 = r1 map R(row.id, row.name, row.value + 1, 0)
by_name = r1 where row.name == "A"
by_value = r1 where row.value > 25
show r2
show by_name
show by_value
'''


def test_global_fanout_unions_requirements_across_consumers():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    requirements = dict(pipeline.global_plan_cost.record_fanout_field_requirements)
    assert 'r1' in requirements
    # by_name needs name, by_value needs value, while r2's recomputation of
    # value needs age. The unrelated `unused` field is not needed by any branch.
    assert set(requirements['r1']) == {'id', 'name', 'value', 'age'}
    assert 'unused' not in requirements['r1']
    assert pipeline.selected_execution_plan.record_plan.record_fanout_field_requirements == tuple(
        sorted(pipeline.global_plan_cost.record_fanout_field_requirements)
    )


def test_backend_emits_shared_fanout_retention_boundary():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'record_fanout_fields = ' in text
    assert 'slang_record_mixed_mask_fields' in text
    assert 'record_fanout_fields = "age,id,name,value"' in text
