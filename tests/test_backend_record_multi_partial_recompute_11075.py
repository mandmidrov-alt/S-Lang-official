from types import SimpleNamespace
from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir

def test_transitive_partial_recompute_unions_multiple_roots_and_direct_fields():
    source = '''
record Person:
    id: Number
    score: Number
    bonus: Number
    name: Text
record R1:
    id: Number
    score: Number
    bonus: Number
    name: Text
record R2:
    id: Number
    score: Number
    bonus: Number
    name: Text
record R3:
    id: Number
    score: Number
    bonus: Number
    name: Text
let people = [Person(1, 5, 7, "A")]
r1 = people map R1(row.id, row.score + 1, row.bonus + 2, row.name)
r2 = r1 map R2(row.id, row.score * 2, row.bonus * 3, row.name)
r3 = r2 map R3(row.id, row.score - 5, row.bonus + 4, row.name)
selected = r3 map R3(row.id, row.score + 1, row.bonus + 1, row.name)
show selected
'''
    module = parse(source)
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    selected = pipeline.selected_execution_plan
    rp = SimpleNamespace(mode='partial', fused_segments=(), materialization_boundaries=('r3',), field_strategies=(
        ('r3', 'selected:map', 'score', 'partial-recompute', 0.42, ('score',)),
        ('r3', 'selected:map', 'bonus', 'partial-recompute', 0.43, ('bonus',)),
        ('r3', 'selected:map', 'id', 'full', 0.10, ('id',)),
    ))
    object.__setattr__(selected, 'record_plan', rp)
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'transitive_recompute_chain_masked' in text
    assert text.count('@slang_record_mixed_map_fields_expr') >= 3
    assert 'chain_fields' in text
