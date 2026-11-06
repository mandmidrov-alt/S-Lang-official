import sys
sys.path.insert(0, '.')

from slang.core import parse
from slang.runtime import execute


def test_physics_executes_from_selected_plan():
    src = open('examples/two_body.sl').read()
    p, trace = execute(parse(src))
    assert trace.executor == 'plan-runtime-physics'
    assert any(step.strategy == 'physics-domain' for step in trace.steps)
    assert any(step.strategy == 'generic' for step in trace.steps)
    earth = next(b for b in p.bodies if b.name == 'earth')
    assert abs(earth.fields['position'].value - 152194895551.0479) < 1e-3
    assert abs(earth.fields['velocity'].value - 30283.78894717536) < 1e-9


def test_physics_plan_contains_show_dependency():
    from slang.compiler_pipeline import compile_semantic_pipeline
    p = parse(open('examples/two_body.sl').read())
    pipeline = compile_semantic_pipeline(p.ast)
    kinds = {s.node: pipeline.optimized_ir.by_binding()[s.node].kind for s in pipeline.selected_execution_plan.steps}
    physics = next(n for n, k in kinds.items() if k == 'physics.gravity')
    show = next(n for n, k in kinds.items() if k == 'effect:show')
    show_step = next(s for s in pipeline.selected_execution_plan.steps if s.node == show)
    deps = pipeline.optimized_ir.by_binding()[show].dependencies
    assert physics in deps
    assert show_step.strategy == 'generic'
