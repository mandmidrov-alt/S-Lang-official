from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_ir import build_execution_ir


def _source():
    return '''
record Person:
    id: Number
    name: Text
    score: Number
record R1:
    id: Number
    label: Text
    value: Number
let people = [Person(1, "A", 5), Person(2, "B", 7)]
r1 = people map R1(row.id, row.name, row.score + 1)
r2 = r1 map R1(row.id, row.label, row.value + 2)
r3 = r2 map R1(row.id, row.label, row.value + 3)
selected = r1 where row.id > 0
'''


def test_record_map_provenance_tracks_direct_and_derived_fields():
    program = parse(_source())
    validate(program)
    ir = build_execution_ir(program.ast)
    r1 = next(n for n in ir.nodes if n.result == 'r1')
    assert r1.record_field_provenance == (
        ('id', ('id',), 'direct'),
        ('label', ('name',), 'direct'),
        ('value', ('score',), 'derived'),
    )


def test_recompute_requires_known_provenance():
    program = parse(_source())
    validate(program)
    cost = compile_semantic_pipeline(program.ast).global_plan_cost
    assert cost.record_recompute_provenance
    assert any(detail for _, _, detail in cost.record_recompute_provenance)
    assert cost.record_recompute_cost > 0


def test_projection_and_recompute_can_coexist_for_same_record_endpoint():
    program = parse(_source())
    validate(program)
    cost = compile_semantic_pipeline(program.ast).global_plan_cost
    modes = {mode for _, mode, _, _ in cost.record_materialization_strategies}
    assert 'projected' in modes
    assert 'recompute' in modes
