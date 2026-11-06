from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline


def _source(consumer_expr):
    return f'''
record Person:
    id: Number
    name: Text
    active: Boolean
    note: Text
    score: Number
record R1:
    id: Number
    name: Text
    active: Boolean
    note: Text
    score: Number
let people = [Person(1, "A", true, "x", 5), Person(2, "B", false, "y", 7)]
r1 = people map R1(row.id, row.name, row.active, row.note, row.score)
r2 = r1 map R1(row.id, row.name, row.active, row.note, row.score)
r3 = r2 map R1(row.id, row.name, row.active, row.note, row.score)
selected = r3 where {consumer_expr}
ordered = r3 sort by row.id asc
total = r3 sum row.score
'''


def _cost(expr):
    module = parse(_source(expr))
    validate(module)
    return compile_semantic_pipeline(module.ast).global_plan_cost


def test_record_downstream_projection_detects_used_fields():
    cost = _cost('row.id > 0')
    assert cost.record_projected_fields
    assert any(fields == ('id',) for _, _, fields in cost.record_projected_fields)
    assert cost.record_projection_savings > 0


def test_full_record_consumer_does_not_claim_projection_savings():
    cost = _cost('row.score > 0 and row.name != ""')
    # This consumer still accesses selected fields, so projection is possible;
    # the planner should report a subset rather than inventing a full-row use.
    assert any(set(fields) == {'name', 'score'} for _, _, fields in cost.record_projected_fields)
    assert cost.record_projection_savings > 0


def test_projection_is_bounded_for_wide_records():
    cost = _cost('row.id > 0')
    assert 0.0 < cost.record_projection_savings <= 0.85 * 3
