from pathlib import Path
from slang.core import parse_file, parse, validate
from slang.execution_ir import build_execution_ir
from slang.execution_plan import build_execution_plan


def test_execution_plan_selects_parallel_group_for_independent_read_only_goals():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    plan = build_execution_plan(build_execution_ir(p.ast))
    assert plan.steps
    assert any(step.mode == 'parallel' for step in plan.steps)
    assert plan.selected_parallel_groups


def test_execution_plan_keeps_io_sequential():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'effects.sl')
    validate(p)
    plan = build_execution_plan(build_execution_ir(p.ast))
    show_steps = [s for s in plan.steps if any(n.startswith('@show:') for n in s.nodes)]
    assert show_steps
    assert all(s.mode == 'sequential' for s in show_steps)


def test_execution_plan_exposes_specialized_collection_backend_candidates():
    p = parse_file(Path(__file__).parents[1] / 'benchmarks' / 'data' / 'filter_sort.sl')
    validate(p)
    plan = build_execution_plan(build_execution_ir(p.ast))
    assert any(backend == 'collection-filter' for _, backend in plan.specialized_candidates)


def test_execution_plan_is_deterministic():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    ir = build_execution_ir(p.ast)
    assert build_execution_plan(ir) == build_execution_plan(ir)
