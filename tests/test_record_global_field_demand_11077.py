from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


def _source():
    return '''
record Person:
    id: Number
    age: Number
    score: Number
record R:
    id: Number
    value: Number
    score2: Number
let people = [Person(1, 20, 3)]
r1 = people map R(row.id, row.age + 1, row.score * 2)
r2 = r1 map R(row.id, row.value * 2, row.score2 + 1)
r3 = r2 map R(row.id, row.value + 4, row.score2)
show r3
'''


def test_global_record_demand_propagates_back_through_map_chain():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    requirements = dict(pipeline.global_plan_cost.record_fanout_field_requirements)
    # The terminal demand is propagated backwards through the Record chain.
    assert 'r3' in requirements
    assert 'r2' in requirements
    assert 'r1' in requirements
    assert set(requirements['r3']) == {'id', 'value', 'score2'}
    assert set(requirements['r2']) == {'id', 'value', 'score2'}
    assert set(requirements['r1']) == {'id', 'value', 'score2'}
    assert pipeline.selected_execution_plan.record_plan.record_fanout_field_requirements == tuple(
        sorted(pipeline.global_plan_cost.record_fanout_field_requirements)
    )


def test_backend_emits_transitive_demand_metadata():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'record_fanout_fields = ' in text
    assert 'record_fanout_fields = "id,score2,value"' in text
