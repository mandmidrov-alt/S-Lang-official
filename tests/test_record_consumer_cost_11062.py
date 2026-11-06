from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline

_BASE = """
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
"""

def _compile(extra):
    module = parse(_BASE + extra)
    validate(module)
    return compile_semantic_pipeline(module.ast)

def test_heavy_consumer_has_higher_record_downstream_cost():
    light = _compile("branch = r2 where row.value > 20\nshow r3\n")
    heavy = _compile("ordered = r2 sort by row.value asc\nshow r3\n")
    assert heavy.global_plan_cost.record_downstream_cost > light.global_plan_cost.record_downstream_cost
    assert any(":sort" in item[1] for item in heavy.global_plan_cost.record_downstream_consumers)

def test_aggregate_consumer_is_priced_above_filter_consumer():
    filtered = _compile("branch = r2 where row.value > 20\nshow r3\n")
    aggregated = _compile("total = r2 sum row.value\nshow r3\n")
    assert aggregated.global_plan_cost.record_downstream_cost > filtered.global_plan_cost.record_downstream_cost
    assert any(":aggregate" in item[1] for item in aggregated.global_plan_cost.record_downstream_consumers)
