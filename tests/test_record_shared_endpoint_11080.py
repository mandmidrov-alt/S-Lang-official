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


def test_shared_endpoint_uses_explicit_reuse_abi():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'selected shared Record endpoint: r2' in text
    assert '@slang_record_f64_share(%v2)' in text
    assert '@slang_record_f64_materialize(%v2)' not in text
    assert text.count('%v2_materialized') >= 3


def test_shared_endpoint_remains_single_handle():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert text.count('@slang_record_f64_share(%v2)') == 1
    assert '%v3 = func.call @slang_record_f64_map_field(%v2_materialized' in text
    assert '%v4 = func.call @slang_record_f64_map_field(%v2_materialized' in text
