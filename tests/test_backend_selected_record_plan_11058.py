from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


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


def test_backend_lowers_selected_full_record_fusion_as_one_runtime_transform():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    assert pipeline.selected_execution_plan.record_plan.mode == 'full'
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert sum(1 for line in text.splitlines() if 'func.call @slang_record_mixed_map_to_schema_expr' in line) == 1
    assert 'func.call @slang_map(' not in text
    assert 'selected Record materialization boundary' not in text


def test_backend_emits_real_materialization_boundary_for_selected_partial_plan():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    # Force a legal partial alternative through the authoritative selected plan.
    from types import SimpleNamespace
    rp = SimpleNamespace(
        mode='partial',
        fused_segments=(('people', 'a'), ('a', 'b', 'c')),
        materialization_boundaries=('a',),
    )
    selected = pipeline.selected_execution_plan
    object.__setattr__(selected, 'record_plan', rp)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert '@slang_record_mixed_materialize' in text
    assert 'selected Record materialization boundary: a' in text
