from slang.core import parse, validate
from slang.optimizer import optimize_program


def _base(consumer):
    return f'''\
record Person:
    name: Text
    age: Number
    active: Boolean
record Summary:
    label: Text
    value: Number
    ok: Boolean
let people = [Person("A", 20, true), Person("B", 30, false)]
summaries = people map Summary(row.name, row.age + 1, row.active)
finals = summaries map Summary(row.label, row.value + 1, row.ok)
{consumer.replace("summaries", "finals")}
'''


def test_downstream_filter_is_recorded():
    p = parse(_base('selected = summaries where row.ok'))
    validate(p)
    r = optimize_program(p)
    d = p._record_fusion_decisions[0]
    assert d.materialization_boundaries == ()
    assert r.record_downstream_pressure >= 1.0


def test_downstream_sort_pressure_changes_long_chain_plan():
    src = '''
record R0:
    value: Number
record R1:
    value: Number
record R2:
    value: Number
record R3:
    value: Number
let people = [R0(1), R0(2)]
r1 = people map R1(row.value + 1)
r2 = r1 map R2(row.value + 1)
r3 = r2 map R3(row.value + 1)
sorted = r3 sort by row.value asc
'''
    p = parse(src)
    validate(p)
    r = optimize_program(p)
    d = p._record_fusion_decisions[0]
    assert d.mode in {'full', 'partial'}
    assert r.record_downstream_pressure >= 2.5


def test_multiple_consumers_are_reported_and_block_unsafe_fusion():
    p = parse(_base('a = finals where row.ok\nb = finals map Summary(row.label, row.value + 2, row.ok)'))
    validate(p)
    r = optimize_program(p)
    assert r.record_transform_fusions == 1
    assert r.record_downstream_fanout >= 2
    assert any(getattr(op, "source", None) == "finals" for op in p.ast.maps + p.ast.filters)
