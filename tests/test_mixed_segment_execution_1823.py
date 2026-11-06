from dataclasses import replace
from types import SimpleNamespace

from slang.compiler_pipeline import compile_semantic_pipeline
from slang.core import parse
from slang.reference_runtime import segment_executor
from slang.runtime import _execute_segmented
from slang.selected_execution_plan import ExecutionSegment
from slang.segment_bridge import capture


def _pipeline_with_manual_segments(module, first, middle, last):
    pipeline = compile_semantic_pipeline(module.ast)
    selected = pipeline.selected_execution_plan
    segments = (
        ExecutionSegment(0, "plan-runtime", (0,), (first,), (selected.by_node()[first].strategy,), (first,), (first,)),
        ExecutionSegment(1, "reference-interpreter", (1,), (middle,), (selected.by_node()[middle].strategy,), (middle,), (middle,)),
        ExecutionSegment(2, "plan-runtime", (2,), (last,), (selected.by_node()[last].strategy,), (last,), (last,)),
    )
    patched = replace(selected, segments=segments)
    return replace(pipeline, selected_execution_plan=patched)


def test_physics_reference_adapter_executes_only_physics_segment():
    module = parse("""
physics gravity
body Moon:
    mass 7.342e22 kg
    position 1 m
    velocity 0 mps
body Probe:
    mass 1000 kg
    position 10 m
    velocity 0 mps
simulate Probe around Moon for 1 s step 1 s
show Probe
""")
    module.bodies = module.ast.bodies
    module.simulation = ("Probe", "Moon", 1.0, 1.0)
    module._bindings = {"before": 7}
    module._collections = {}
    module._states = {}
    module.entities = {}
    ir_pipeline = compile_semantic_pipeline(module.ast)
    node = next(step.node for step in ir_pipeline.selected_execution_plan.steps
                if ir_pipeline.optimized_ir.by_binding()[step.node].kind == "physics.gravity")
    segment = SimpleNamespace(index=1, mode="reference-interpreter", nodes=(node,))
    handoff = capture(module, 1, "reference-interpreter")
    segment_executor(module, segment, handoff)
    assert module._bindings["before"] == 7
    assert module._physics_result == ("Probe", "Moon")
    assert module.bodies[1].fields["position"].value > 10


def test_mixed_plan_reference_plan_preserves_shared_namespace():
    module = parse("""
let a = 2
let b = a + 3
let c = b * 4
""")
    pipeline = compile_semantic_pipeline(module.ast)
    nodes = [step.node for step in pipeline.selected_execution_plan.steps]
    assert [n.split("#", 1)[0] for n in nodes[:3]] == ["a", "b", "c"]
    pipeline = _pipeline_with_manual_segments(module, *nodes[:3])
    _execute_segmented(module, pipeline)
    assert module._bindings["a"] == 2
    assert module._bindings["b"] == 5
    assert module._bindings["c"] == 20


def test_reference_segment_never_restarts_whole_program():
    module = parse("""
let a = 2
let b = a + 3
let c = b + 4
""")
    pipeline = compile_semantic_pipeline(module.ast)
    nodes = [step.node for step in pipeline.selected_execution_plan.steps]
    pipeline = _pipeline_with_manual_segments(module, *nodes[:3])
    module._segment_runtime_initialized = False
    _execute_segmented(module, pipeline)
    assert module._bindings == {"a": 2, "b": 5, "c": 9}
