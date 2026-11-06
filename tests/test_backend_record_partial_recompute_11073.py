from types import SimpleNamespace
from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


def _source():
    return '''
record Person:
    score: Number
    value: Number
let people = [Person(2, 3)]
a = people map Person(row.score, row.score * 2)
b = a map Person(row.score, row.value + 1)
show b
'''


def test_backend_lowers_partial_recompute_with_minimal_source_mask():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    selected = pipeline.selected_execution_plan
    rp = SimpleNamespace(
        mode='partial',
        fused_segments=(),
        materialization_boundaries=('a',),
        field_strategies=(('a', 'b:map', 'value', 'partial-recompute', 0.42, ('score',)),),
    )
    object.__setattr__(selected, 'record_plan', rp)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert '@slang_record_f64_mask_fields' in text
    assert '@slang_record_f64_map_fields_expr' in text
    assert 'record_field_plan = "value:partial-recompute:0.42:score"' in text
    assert 'transitive_recompute_chain_masked' in text
