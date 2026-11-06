from types import SimpleNamespace
from slang.global_plan_optimizer import _record_plan_downstream_cost


def test_record_field_strategies_are_selected_independently():
    schema = SimpleNamespace(fields=(
        SimpleNamespace(name='id', type_name='Number'),
        SimpleNamespace(name='score', type_name='Number'),
        SimpleNamespace(name='value', type_name='Text'),
    ))
    parent = SimpleNamespace(
        binding='r1', kind='map', pure=True, deterministic=True,
        output_schema=schema, input_schema=schema,
        record_field_provenance=(
            ('id', ('id',), 'direct'),
            ('score', ('score',), 'direct'),
            ('value', ('score',), 'derived'),
        ),
    )
    child = SimpleNamespace(binding='r2', kind='map', pure=True, deterministic=True, memory_region_specs=(
        SimpleNamespace(selector='*', path=('id',), scope='element'),
        SimpleNamespace(selector='*', path=('value',), scope='element'),
    ))
    ir = SimpleNamespace(by_binding=lambda: {'r1': parent, 'r2': child}, nodes=(parent, child))
    record_plan = SimpleNamespace(fused_segments=(('r1',),))
    result = _record_plan_downstream_cost(
        record_plan,
        {'r1': 'fused-record', 'r2': 'fused-record'},
        {'r1': SimpleNamespace(node='r1', scores=(('fused-record', 1.0),)),
         'r2': SimpleNamespace(node='r2', scores=(('fused-record', 1.0),))},
        (SimpleNamespace(before='r1', after='r2'),),
        ir,
        {'r1': 10.0, 'r2': 10.0},
    )
    strategies = result[-1]
    assert strategies
    by_field = {row[2]: row[3] for row in strategies}
    assert 'id' in by_field
    assert 'value' in by_field
    assert by_field['value'] in {'partial-recompute', 'recompute', 'projected'}
