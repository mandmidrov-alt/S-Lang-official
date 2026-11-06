from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


def _source():
    return '''
record Person:
    id: Number
    score: Number
record R:
    id: Number
    value: Number
let people = [Person(1, 3)]
r1 = people map R(row.id, row.score * 2)
r2 = r1 map R(row.id, row.value + 1)
r3 = r2 map R(row.id, row.value + 3)
r4 = r2 map R(row.id, row.value * 2)
show r3
show r4
'''


def test_global_plan_records_shared_recompute_candidate():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    decisions = tuple(pipeline.global_plan_cost.record_shared_recompute_decisions)
    assert decisions
    assert any(endpoint == 'r2' and field == 'value' for endpoint, field, *_ in decisions)
    assert pipeline.global_plan_cost.record_shared_recompute_savings >= 0.0
    assert pipeline.selected_execution_plan.record_plan.record_shared_recompute_decisions == decisions


def test_backend_emits_shared_recompute_metadata():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'S-Lang Record shared recompute:' in text


def test_backend_executes_shared_recompute_at_shared_endpoint():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    # The shared endpoint r2 must survive structural fusion and be emitted once.
    assert 'node = "r2#1"' in text
    # Both downstream maps must consume the shared r2 handle rather than a
    # fused copy that independently recomputes r2 from the original source.
    assert 'node = "r3#1"' in text
    assert 'node = "r4#1"' in text
    assert 'record_shared_recompute' in text
    assert text.count('node = "r2#1"') == 1
    # The two branches must reference the materialized shared handle emitted at r2.
    assert '%v2_materialized' in text
    assert '%v3 = func.call @slang_record_f64_map_field(%v2_materialized' in text
    assert '%v4 = func.call @slang_record_f64_map_field(%v2_materialized' in text


def test_backend_shared_endpoint_is_not_recomputed_per_branch():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    # There is exactly one lowered r2 endpoint; r3/r4 consume its materialized
    # handle rather than independently reconstructing r2.
    assert text.count('node = "r2#1"') == 1
    assert text.count('func.call @slang_record_f64_share(%v2)') == 1
    assert text.count('%v2_materialized') >= 3
