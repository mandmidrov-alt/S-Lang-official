from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_ir import build_execution_ir
from slang.global_plan_optimizer import _record_recompute_provenance


def _source():
    return '''
record Person:
    id: Number
    score: Number
    name: Text
record R1:
    id: Number
    value: Number
    label: Text
record R2:
    id: Number
    value: Number
    label: Text
record R3:
    id: Number
    value: Number
    label: Text
let people = [Person(1, 5, "A"), Person(2, 7, "B")]
r1 = people map R1(row.id, row.score + 1, row.name)
r2 = r1 map R2(row.id, row.value * 2, row.label)
r3 = r2 map R3(row.id, row.value - 5, row.label)
selected = r3 map R3(row.id, row.value + 1, row.label)
'''


def test_record_provenance_resolves_through_multiple_maps():
    program = parse(_source())
    validate(program)
    ir = build_execution_ir(program.ast)
    r3 = next(n for n in ir.nodes if n.result == 'r3')
    assert r3.record_field_provenance == (
        ('id', ('id',), 'direct'),
        ('value', ('score',), 'derived'),
        ('label', ('name',), 'direct'),
    )


def test_transitive_provenance_is_used_by_recompute_planning():
    program = parse(_source())
    validate(program)
    ir = build_execution_ir(program.ast)
    r3 = next(n for n in ir.nodes if n.result == 'r3')
    selected = next(n for n in ir.nodes if n.result == 'selected')
    ok, complexity, detail = _record_recompute_provenance(r3, selected, ('value',))
    assert ok
    assert complexity > 0
    assert ('value', ('score',), 'derived') in detail
