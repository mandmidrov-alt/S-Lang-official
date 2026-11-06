from pathlib import Path
import tempfile

from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir
from slang.execution_plan import build_execution_plan
from slang.execution_scheduler import build_schedule
from slang.dependency_graph import build_dependency_graph
from slang.dependency_analysis import analyze_dependency_graph
from slang.conflict_graph import group_is_conflict_free


def load(text):
    p = Path(tempfile.mktemp(suffix='.sl'))
    p.write_text(text)
    try:
        x = parse_file(p)
        validate(x)
        return x
    finally:
        p.unlink(missing_ok=True)


def test_conflicting_state_writes_are_never_parallel():
    ir = build_execution_ir(load('state x = 0\nset x = 1\nset x = 2\n').ast)
    writes = [n for n in ir.nodes if n.kind == 'state:set']
    plan = build_execution_plan(ir)
    assert all(step.mode != 'parallel' for step in plan.steps)
    assert not group_is_conflict_free(ir, [n.binding for n in writes])


def test_conflicting_read_write_is_not_parallel_even_if_read_is_safe():
    ir = build_execution_ir(load('state x = 0\nlet a = x + 1\nset x = 2\n').ast)
    plan = build_execution_plan(ir)
    assert all(step.mode != 'parallel' for step in plan.steps)
    graph = build_dependency_graph(ir)
    analysis = analyze_dependency_graph(ir, graph)
    assert not any(set(group) >= {n.binding for n in ir.nodes if n.result == 'a'} for group in analysis.parallel_safe_candidates)


def test_independent_state_reads_remain_parallel_safe():
    ir = build_execution_ir(load('state x = 0\nstate y = 0\nlet a = x + 1\nlet b = y + 1\n').ast)
    plan = build_execution_plan(ir)
    schedule = build_schedule(ir)
    assert any(step.mode == 'parallel' for step in plan.steps)
    assert any(schedule.parallel_safe_batches)
