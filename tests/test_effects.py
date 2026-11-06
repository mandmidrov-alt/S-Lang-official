from pathlib import Path
from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir
from slang.execution_scheduler import build_schedule


def _program():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'effects.sl')
    validate(p)
    return p


def test_show_is_a_real_io_effect_node():
    ir = build_execution_ir(_program().ast)
    effects = [n for n in ir.nodes if n.kind == 'effect:show']
    assert len(effects) == 2
    assert all(n.effects == ('IO',) for n in effects)
    assert all(not n.pure and not n.parallel_safe for n in effects)
    assert all(n.order_sensitive for n in effects)


def test_show_effects_are_ordered():
    ir = build_execution_ir(_program().ast)
    effects = [n for n in ir.nodes if n.kind == 'effect:show']
    assert effects[0].binding in effects[1].dependencies
    schedule = build_schedule(ir)
    positions = {name: i for i, name in enumerate(schedule.order)}
    assert positions[effects[0].binding] < positions[effects[1].binding]


def test_effective_batch_is_not_parallel_safe():
    ir = build_execution_ir(_program().ast)
    schedule = build_schedule(ir)
    effect_positions = {n.binding: i for i, n in enumerate(ir.nodes) if n.kind == 'effect:show'}
    assert any(not schedule.parallel_safe_batches[i] for i, batch in enumerate(schedule.batches) if any(x in effect_positions for x in batch))
