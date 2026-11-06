"""Compatibility boundary for the verified reference interpreter.

The plan runtime must not depend directly on ``core``.  Unsupported programs
cross this module-level boundary explicitly, keeping the reference interpreter
isolated from the normal plan execution path.
"""
from __future__ import annotations


def execute(module):
    """Execute *module* with the verified reference interpreter."""
    from .core import run as reference_run
    return reference_run(module)


def execute_segment(module, segment, handoff):
    """Execute one reference-only segment without restarting the program.

    This is the first concrete segment adapter.  It intentionally supports a
    narrow, expression-backed binding boundary.  The adapter uses the legacy
    evaluator only for the nodes assigned to this segment, while preserving the
    namespace established by the preceding plan-runtime segment.
    """
    from .core import _eval_expr
    from .ast import BindingDecl

    bindings = {b.name: b for b in getattr(module.ast, "bindings", ())}
    for node in segment.nodes:
        name = node.rsplit("#", 1)[0]
        binding = bindings.get(name)
        if binding is None:
            raise RuntimeError(
                f"reference segment adapter does not support node '{node}'"
            )
        value = _eval_expr(binding.expr, module)
        if isinstance(value, list):
            module._collections[name] = value
        else:
            module._bindings[name] = value
    return module


def execute_filter_segment(module, segment, handoff):
    """Execute a reference-selected filter against the shared collection namespace.

    This adapter is used when a backend permits the semantic ``generic``
    strategy for a filter but the unified runtime has no direct generic-filter
    contract. It evaluates only the assigned filter nodes and preserves the
    existing plan-runtime namespace.
    """
    from .plan_expression import eval_expr

    filters = {op.result: op for op in getattr(module.ast, "filters", ())}
    for node in segment.nodes:
        name = node.rsplit("#", 1)[0]
        op = filters.get(name)
        if op is None:
            raise RuntimeError(f"reference filter adapter does not support node '{node}'")
        if op.source not in module._collections:
            raise RuntimeError(f"collection source '{op.source}' is not available for '{name}'")
        values = module._collections[op.source]
        out = []
        for row in values:
            value = eval_expr(op.predicate.expr, module, row=row)
            if not isinstance(value, bool):
                raise TypeError(f"filter predicate for '{name}' must evaluate to Boolean")
            if value:
                out.append(row)
        module._collections[name] = out
    return module


def execute_physics_segment(module, segment, handoff):
    """Execute one gravity-domain segment through the reference semantics.

    This adapter is intentionally narrow: it handles exactly the simulation
    represented by the physics IR node and mutates the already shared entity
    namespace. It never initializes or re-runs unrelated program nodes.
    """
    import math
    from .plan_runtime_support import Quantity

    simulations = list(getattr(module.ast, "simulations", ()) or ())
    if len(simulations) != 1:
        raise RuntimeError("reference physics segment requires exactly one simulation")
    sim = simulations[0]
    bodies = {body.name: body for body in getattr(module, "bodies", ())}
    target = bodies.get(sim.target)
    attractor = bodies.get(sim.attractor)
    if target is None or attractor is None:
        raise TypeError("simulate refers to unknown body")
    if "position" not in target.fields or "velocity" not in target.fields:
        raise TypeError(f"{sim.target} requires position and velocity for gravity simulation")
    if "mass" not in attractor.fields:
        raise TypeError(f"{sim.attractor} requires mass")

    duration = sim.duration
    step_size = sim.step
    if duration <= 0 or step_size <= 0:
        raise TypeError("simulation duration and step must be positive")
    steps = int(math.floor(duration / step_size + 1e-12))
    remainder = duration - steps * step_size
    G = 6.67430e-11
    for k in range(steps + (1 if remainder > 1e-12 else 0)):
        dt = step_size if k < steps else remainder
        position = target.fields["position"]
        velocity = target.fields["velocity"]
        mass = attractor.fields["mass"]
        acceleration = G * mass.value / (position.value * position.value)
        target.fields["velocity"] = Quantity(velocity.value + acceleration * dt, "mps")
        target.fields["position"] = Quantity(position.value + target.fields["velocity"].value * dt, "m")
    module._physics_result = (sim.target, sim.attractor)
    return module


def segment_executor_registry():
    """Built-in reference adapters keyed by semantic execution kind."""
    return {
        "binding": execute_segment,
        # Grouping calls are represented as their own semantic IR kind, but
        # their reference semantics are still ordinary binding evaluation.
        # Keep them on the shared module namespace so upstream collections
        # and downstream consumers remain visible across segment boundaries.
        "group": execute_segment,
        "filter": execute_filter_segment,
        "physics.gravity": execute_physics_segment,
    }

def segment_executor(module, segment, handoff):
    """Dispatch reference nodes individually through registered adapters."""
    from .execution_ir import build_execution_ir

    ir = build_execution_ir(module.ast)
    by_binding = ir.by_binding()
    registry = segment_executor_registry()
    node_kinds = {node: (by_binding[node].kind if node in by_binding else "unknown") for node in segment.nodes}
    kinds = tuple(dict.fromkeys(node_kinds.values()))
    missing = tuple(kind for kind in kinds if kind not in registry)
    if missing:
        raise RuntimeError(
            "no reference segment adapter for kinds: " + ", ".join(sorted(missing))
        )
    from types import SimpleNamespace
    for kind in kinds:
        nodes = tuple(node for node in segment.nodes if node_kinds.get(node) == kind)
        subsegment = SimpleNamespace(index=segment.index, mode=segment.mode, nodes=nodes)
        registry[kind](module, subsegment, handoff)
    return module
