"""Semantic execution planning for S-Lang.

The planner converts DependencyGraph analysis into an explicit, deterministic
plan. It does not execute anything and does not claim that a specialized or
parallel backend exists; backend candidates are advisory metadata for later
lowering stages.
"""
from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR
from .dependency_graph import DependencyGraph, build_dependency_graph
from .dependency_analysis import DependencyAnalysis, analyze_dependency_graph
from .fusion import FusionGroup, find_fusion_groups
from .conflict_graph import group_is_conflict_free

_SPECIALIZED_BACKENDS = {
    "filter": "collection-filter",
    "sort": "collection-sort",
    "map": "collection-map",
    "aggregate": "collection-aggregate",
    "reduce": "collection-reduce",
    "sequence": "sequence-engine",
    "goal:select": "goal-selection",
    "goal:path": "graph-search",
    "goal:satisfy": "constraint-solver",
    "physics.gravity": "physics-backend",
}

@dataclass(frozen=True)
class ExecutionPlanStep:
    level: int
    nodes: tuple[str, ...]
    mode: str  # sequential | parallel | batch
    backend: str
    backend_candidates: tuple[str, ...]
    input_type: str | None = None
    output_type: str | None = None
    type_contracts: tuple[tuple[str, str | None, str | None], ...] = ()

@dataclass(frozen=True)
class ExecutionPlan:
    steps: tuple[ExecutionPlanStep, ...]
    critical_path: tuple[str, ...]
    selected_parallel_groups: tuple[tuple[str, ...], ...]
    specialized_candidates: tuple[tuple[str, str], ...]
    fusion_groups: tuple[FusionGroup, ...] = ()

    @property
    def operation_count(self) -> int:
        return sum(len(step.nodes) for step in self.steps)


def _backend_candidates(node) -> tuple[str, ...]:
    candidates = ["generic"]
    specialized = _SPECIALIZED_BACKENDS.get(node.kind)
    if specialized:
        candidates.append(specialized)
    if node.parallel_safe:
        candidates.append("parallel-generic")
    return tuple(candidates)


def build_execution_plan(
    ir: ExecutionIR,
    analysis: DependencyAnalysis | None = None,
    graph: DependencyGraph | None = None,
    backend_supported_strategies: tuple[str, ...] | None = None,
) -> ExecutionPlan:
    graph = graph or build_dependency_graph(ir)
    analysis = analysis or analyze_dependency_graph(ir, graph)
    by = ir.by_binding()
    steps: list[ExecutionPlanStep] = []
    parallel_groups: list[tuple[str, ...]] = []
    specialized: list[tuple[str, str]] = []
    fusion_groups = find_fusion_groups(ir)
    if backend_supported_strategies is not None:
        allowed = set(backend_supported_strategies)
        fusion_groups = tuple(g for g in fusion_groups if g.strategy in allowed)

    for level, group in enumerate(analysis.levels):
        nodes = tuple(group)
        safe = len(nodes) > 1 and all(by[n].parallel_safe for n in nodes) and group_is_conflict_free(ir, nodes)
        if safe:
            mode = "parallel"
            backend = "parallel-generic"
            parallel_groups.append(nodes)
        elif len(nodes) > 1:
            mode = "batch"
            backend = "generic"
        else:
            mode = "sequential"
            backend = "generic"

        candidates = sorted(set(c for n in nodes for c in _backend_candidates(by[n])))
        if backend_supported_strategies is not None:
            allowed = set(backend_supported_strategies)
            candidates = [c for c in candidates if c in allowed]
        for n in nodes:
            for candidate in _backend_candidates(by[n]):
                if candidate != "generic" and candidate != "parallel-generic":
                    specialized.append((n, candidate))
        steps.append(ExecutionPlanStep(
            level, nodes, mode, backend, tuple(candidates),
            input_type=by[nodes[0]].input_type if len(nodes) == 1 else None,
            output_type=by[nodes[0]].output_type if len(nodes) == 1 else None,
            type_contracts=tuple((n, by[n].input_type, by[n].output_type) for n in nodes),
        ))

    return ExecutionPlan(
        steps=tuple(steps),
        critical_path=analysis.critical_path,
        selected_parallel_groups=tuple(parallel_groups),
        specialized_candidates=tuple(sorted(set(specialized))),
        fusion_groups=fusion_groups,
    )


def format_execution_plan(plan: ExecutionPlan) -> str:
    lines = ["execution.plan {"]
    for step in plan.steps:
        lines.append(f"  step {step.level}: mode={step.mode} backend={step.backend}")
        if len(step.nodes) == 1:
            lines.append(f"    type = {step.input_type or 'unknown'} -> {step.output_type or 'unknown'}")
        else:
            lines.append("    types = " + ", ".join(f"{n}:{i or 'unknown'}->{o or 'unknown'}" for n, i, o in step.type_contracts))
        lines.append("    nodes = " + ", ".join(step.nodes))
        lines.append("    backend_candidates = " + ", ".join(step.backend_candidates))
    lines.append(f"  steps = {len(plan.steps)}")
    lines.append(f"  operations = {plan.operation_count}")
    lines.append("  critical_path = " + (" -> ".join(plan.critical_path) if plan.critical_path else "none"))
    lines.append(f"  selected_parallel_groups = {len(plan.selected_parallel_groups)}")
    for i, group in enumerate(plan.selected_parallel_groups):
        lines.append(f"  parallel_group {i}: " + ", ".join(group))
    lines.append(f"  fusion_groups = {len(plan.fusion_groups)}")
    for group in plan.fusion_groups:
        lines.append(f"  fusion {group.strategy} mode={group.mode} materializes={'yes' if group.materializes else 'no'} prefix={group.fused_prefix_length}: " + " -> ".join(group.nodes))
    lines.append(f"  specialized_candidates = {len(plan.specialized_candidates)}")
    for node, backend in plan.specialized_candidates:
        lines.append(f"  specialized {node}: {backend}")
    lines.append("  parallel_safety = conflict-aware-static")
    lines.append("  execution = plan-only")
    lines.append("  backend_selection = capability-aware-if-constrained")
    lines.append("}")
    return "\n".join(lines)
