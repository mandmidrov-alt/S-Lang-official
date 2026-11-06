from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline


def _source(field_lines, map_args):
    records = '\n'.join([
        f'record R1:\n{field_lines}',
        f'record R2:\n{field_lines}',
        f'record R3:\n{field_lines}',
    ])
    a1, a2 = map_args
    return f'''\nrecord Person:\n    name: Text\n    age: Number\n{records}\nlet people = [Person("A", 20), Person("B", 30)]\nr1 = people map R1({a1})\nr2 = r1 map R2({a2})\nr3 = r2 map R3({a2})\nselected = r3 where row.value > 20\nordered = r3 sort by row.value asc\ntotal = r3 sum row.value\n'''


def _cost(fields, a1, a2):
    module = parse(_source(fields, (a1, a2)))
    validate(module)
    return compile_semantic_pipeline(module.ast).global_plan_cost


def test_record_schema_width_participates_in_cost():
    narrow_fields = '    name: Text\n    value: Number'
    wide_fields = narrow_fields + '\n    active: Boolean\n    note: Text\n    extra: Text\n    extra2: Text\n    extra3: Number'
    narrow = _cost(narrow_fields, 'row.name, row.age + 1', 'row.name, row.value + 1')
    wide = _cost(wide_fields, 'row.name, row.age + 1, row.age > 0, row.name, row.name, row.name, row.age + 1', 'row.name, row.value + 1, row.value > 0, row.name, row.name, row.name, row.value + 1')
    assert narrow.record_downstream_fanout >= 3
    assert narrow.record_schema_width > 0
    assert narrow.record_materialization_cost > 0
    assert wide.record_schema_width > narrow.record_schema_width
    assert wide.record_materialization_cost > narrow.record_materialization_cost


def test_record_schema_profile_is_bounded_planning_data():
    fields = '    name: Text\n    value: Number'
    cost = _cost(fields, 'row.name, row.age + 1', 'row.name, row.value + 1')
    assert cost.record_schema_complexity >= 1.0
    assert cost.record_materialization_cost < 100.0
