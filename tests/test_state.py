from pathlib import Path
from slang.core import parse_file, validate, run, show_expr_value
from slang.execution_ir import build_execution_ir
from slang.execution_scheduler import build_schedule

def test_state_executes_in_source_order():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'state.sl')
    validate(p); run(p)
    assert p._states['counter'] == 3

def test_state_operations_are_effectful_and_not_parallel_safe():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'state.sl')
    validate(p)
    ir = build_execution_ir(p.ast)
    ops = [n for n in ir.nodes if n.kind in {'state:init','state:set'}]
    assert len(ops) == 3
    assert all(n.effects == ('state',) for n in ops)
    assert all(n.access == 'write' for n in ops)
    assert all(not n.parallel_safe for n in ops)
    schedule = build_schedule(ir)
    pos = {name:i for i,name in enumerate(schedule.order)}
    assert pos[ops[0].binding] < pos[ops[1].binding] < pos[ops[2].binding]
