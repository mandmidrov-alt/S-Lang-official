from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline


def _source():
    return """
record Person:
    name: Text
    age: Number
record R1:
    name: Text
    value: Number
record R2:
    name: Text
    value: Number
record R3:
    name: Text
    value: Number

let people = [Person("A", 20), Person("B", 30)]
r1 = people map R1(row.name, row.age + 1)
r2 = r1 map R2(row.name, row.value + 1)
r3 = r2 map R3(row.name, row.value + 1)
selected = r3 where row.value > 20
ordered = r3 sort by row.value asc
total = r3 sum row.value
"""


def test_global_record_cost_uses_real_fanout_and_consumers():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    cost = pipeline.global_plan_cost

    assert cost is not None
    assert cost.record_downstream_fanout >= 3
    assert cost.record_downstream_cost > 0
    consumers = {(endpoint, child) for endpoint, child, _ in cost.record_downstream_consumers}
    assert any(endpoint == "r3" and child.startswith("selected#") for endpoint, child in consumers)
    assert any(endpoint == "r3" and child.startswith("ordered#") for endpoint, child in consumers)
    assert any(endpoint == "r3" and child.startswith("total#") for endpoint, child in consumers)


def test_record_downstream_term_is_shared_for_fanout():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    cost = pipeline.global_plan_cost

    # The fan-out is three consumers of one shared Record endpoint. The
    # global Record term therefore contains three consumer entries, not three
    # independent materialization penalties.
    assert len(cost.record_downstream_consumers) == 3
    assert cost.record_downstream_fanout == 3
