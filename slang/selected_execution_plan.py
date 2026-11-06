"""Concrete execution plan selected from semantic strategies.

The semantic execution plan describes what can be executed.  This module
records the deterministic strategy actually selected for every operation,
together with its alternatives and resource contract, so later backend stages
consume an explicit artifact rather than recomputing decisions.
"""
from __future__ import annotations
from dataclasses import dataclass
from .cost_model import materialization_profile, resource_profile
from .execution_plan import ExecutionPlan
from .execution_profile import ExecutionProfile
from .strategy_selection import StrategyChoice
from .runtime_capability import runtime_strategy_supported


@dataclass(frozen=True)
class ExecutionStep:
    level: int
    node: str
    strategy: str
    profile: str
    score: float | None
    alternatives: tuple[str, ...]
    memory_model: str
    ordering: str
    parallelism: str
    materialization: str
    execution_mode: str = "materialized"
    input_type: str | None = None
    output_type: str | None = None
    type_contracts: tuple[tuple[str, str | None, str | None], ...] = ()


@dataclass(frozen=True)
class ExecutionRegion:
    """Concrete execution form selected for a contiguous plan region.

    Unlike capability segments, execution regions describe the selected form
    of the plan itself: streaming, materialized, or parallel. They are static
    lowering instructions; they do not claim that a backend has already
    executed the region.
    """
    index: int
    mode: str  # streaming | materialized | parallel
    levels: tuple[int, ...]
    nodes: tuple[str, ...]
    strategies: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionSegment:
    """Contiguous runtime region of the selected plan.

    A segment is either executable by the unified plan-runtime or explicitly
    delegated to the reference interpreter.  Boundaries are deterministic and
    preserve the selected plan order; they are metadata only until a runtime
    backend elects to execute segmented fallback.
    """
    index: int
    mode: str  # plan-runtime | reference-interpreter
    levels: tuple[int, ...]
    nodes: tuple[str, ...]
    strategies: tuple[str, ...]
    entry_nodes: tuple[str, ...] = ()
    exit_nodes: tuple[str, ...] = ()
    data_contract: object | None = None
    execution_mode: str = "materialized"


@dataclass(frozen=True)
class SelectedExecutionPlan:
    steps: tuple[ExecutionStep, ...]
    backend: str | None
    execution_profile: ExecutionProfile
    deterministic: bool = True
    segments: tuple[ExecutionSegment, ...] = ()
    execution_regions: tuple[ExecutionRegion, ...] = ()
    record_plan: object | None = None

    @property
    def operation_count(self) -> int:
        return len(self.steps)

    @property
    def levels(self) -> int:
        return len({step.level for step in self.steps})

    def by_node(self) -> dict[str, ExecutionStep]:
        return {step.node: step for step in self.steps}



def _segment_mode(kind: str, strategy: str, choice_supported: bool) -> str:
    return "plan-runtime" if choice_supported and runtime_strategy_supported(kind, strategy) else "reference-interpreter"


def _execution_mode(strategy: str) -> str:
    memory, _ordering, parallelism = resource_profile(strategy)
    if parallelism == "parallel-where-independent":
        return "parallel"
    if materialization_profile(strategy) == "streaming-when-fused" or memory == "streaming":
        return "streaming"
    return "materialized"


def _build_execution_regions(steps: tuple[ExecutionStep, ...]) -> tuple[ExecutionRegion, ...]:
    """Lower per-step execution contracts into contiguous execution regions."""
    if not steps:
        return ()
    regions = []
    current = [steps[0]]
    current_mode = steps[0].execution_mode
    for step in steps[1:]:
        if step.execution_mode != current_mode:
            regions.append(ExecutionRegion(
                index=len(regions), mode=current_mode,
                levels=tuple(dict.fromkeys(s.level for s in current)),
                nodes=tuple(s.node for s in current),
                strategies=tuple(s.strategy for s in current),
            ))
            current = [step]
            current_mode = step.execution_mode
        else:
            current.append(step)
    regions.append(ExecutionRegion(
        index=len(regions), mode=current_mode,
        levels=tuple(dict.fromkeys(s.level for s in current)),
        nodes=tuple(s.node for s in current),
        strategies=tuple(s.strategy for s in current),
    ))
    return tuple(regions)


def build_selected_execution_plan(
    plan: ExecutionPlan,
    strategies: tuple[StrategyChoice, ...],
    execution_profile: ExecutionProfile,
    backend: str | None = None,
    node_kinds: dict[str, str] | None = None,
    dependency_edges: tuple[object, ...] | None = None,
    ir=None,
    external_names=(),
    record_plan=None,
) -> SelectedExecutionPlan:
    """Bind selected strategies and partition them into runtime segments."""
    choice_by_node = {choice.node: choice for choice in strategies}
    expected = [node for step in plan.steps for node in step.nodes]
    missing = [node for node in expected if node not in choice_by_node]
    extra = [node for node in choice_by_node if node not in set(expected)]
    if missing or extra:
        raise ValueError(f"strategy/plan mismatch: missing={missing!r} extra={sorted(extra)!r}")

    steps: list[ExecutionStep] = []
    kinds = node_kinds or {}
    for semantic_step in plan.steps:
        for node in semantic_step.nodes:
            choice = choice_by_node[node]
            selected_score = next((score for name, score in choice.scores if name == choice.strategy), None)
            memory, ordering, parallelism = resource_profile(choice.strategy)
            materialization = materialization_profile(choice.strategy)
            steps.append(ExecutionStep(
                level=semantic_step.level, node=node, strategy=choice.strategy,
                profile=choice.profile, score=selected_score, alternatives=choice.alternatives,
                memory_model=memory, ordering=ordering, parallelism=parallelism,
                materialization=materialization, execution_mode=_execution_mode(choice.strategy),
                input_type=next((n.input_type for n in (ir.nodes if ir is not None else ()) if n.binding == node), None),
                output_type=next((n.output_type for n in (ir.nodes if ir is not None else ()) if n.binding == node), None),
                type_contracts=((node, next((n.input_type for n in (ir.nodes if ir is not None else ()) if n.binding == node), None), next((n.output_type for n in (ir.nodes if ir is not None else ()) if n.binding == node), None)),),
            ))

    if ir is not None:
        ir_by = ir.by_binding()
        for step in steps:
            node = ir_by.get(step.node)
            if node is None:
                raise ValueError(f"selected plan references unknown IR node: {step.node}")
            if step.input_type != node.input_type or step.output_type != node.output_type:
                raise ValueError(
                    f"execution-plan type contract mismatch for {step.node}: "
                    f"plan={step.input_type!r}->{step.output_type!r}, "
                    f"ir={node.input_type!r}->{node.output_type!r}"
                )

    segments: list[ExecutionSegment] = []
    predecessors: dict[str, set[str]] = {}
    successors: dict[str, set[str]] = {}
    for edge in dependency_edges or ():
        predecessors.setdefault(edge.after, set()).add(edge.before)
        successors.setdefault(edge.before, set()).add(edge.after)
    current_mode: str | None = None
    current: list[ExecutionStep] = []

    def flush() -> None:
        nonlocal current, current_mode
        if not current:
            return
        nodes = tuple(s.node for s in current)
        node_set = set(nodes)
        entry = tuple(
            node for node in nodes
            if any(pred not in node_set for pred in predecessors.get(node, ()))
        ) or (nodes[0],)
        exit_nodes = tuple(
            node for node in nodes
            if any(succ not in node_set for succ in successors.get(node, ()))
        ) or (nodes[-1],)
        segments.append(ExecutionSegment(
            index=len(segments),
            mode=current_mode or "reference-interpreter",
            levels=tuple(dict.fromkeys(s.level for s in current)),
            nodes=nodes,
            strategies=tuple(s.strategy for s in current),
            entry_nodes=entry,
            exit_nodes=exit_nodes,
        ))
        current = []

    for step in steps:
        choice = choice_by_node[step.node]
        mode = _segment_mode(kinds.get(step.node, "binding"), step.strategy, choice.runtime_supported)
        if current_mode is None:
            current_mode = mode
        elif mode != current_mode:
            flush()
            current_mode = mode
        current.append(step)
    flush()

    # Materialize the boundary contracts as part of the static selected plan.
    # This makes the bridge contract inspectable and validates its shape before
    # runtime execution rather than discovering it while crossing a boundary.
    if ir is not None and segments:
        from .segment_bridge import build_segment_data_contracts, validate_segment_contracts
        contracts = build_segment_data_contracts(
            tuple(segments), dependency_edges or (), ir, external_names=external_names,
        )
        validate_segment_contracts(tuple(segments), contracts, dependency_edges or (), ir=ir)
        segments = [
            ExecutionSegment(
                index=segment.index, mode=segment.mode, levels=segment.levels,
                nodes=segment.nodes, strategies=segment.strategies,
                entry_nodes=segment.entry_nodes, exit_nodes=segment.exit_nodes,
                data_contract=contracts.get(segment.index), execution_mode=segment.execution_mode,
            )
            for segment in segments
        ]

    step_tuple = tuple(steps)
    execution_regions = _build_execution_regions(step_tuple)
    selected = SelectedExecutionPlan(
        steps=step_tuple, backend=backend, execution_profile=execution_profile,
        deterministic=True, segments=tuple(segments), execution_regions=execution_regions, record_plan=record_plan,
    )
    from .determinism import validate_segment_determinism
    validate_segment_determinism(selected, ir=ir)
    return selected


def format_selected_execution_plan(plan: SelectedExecutionPlan) -> str:
    lines = ["selected.execution.plan {"]
    lines.append(f"  backend = {plan.backend or 'unspecified'}")
    lines.append(
        "  execution_profile = "
        f"cpu:{plan.execution_profile.cpu_cores} "
        f"parallel:{'yes' if plan.execution_profile.allow_parallelism else 'no'}"
    )
    for step in plan.steps:
        score = "none" if step.score is None else f"{step.score:g}"
        lines.append(f"  step {step.level}.{step.node}: strategy={step.strategy} profile={step.profile} mode={step.execution_mode} score={score}")
        lines.append(f"    type = {step.input_type or 'unknown'} -> {step.output_type or 'unknown'}")
        lines.append(f"    resources = memory:{step.memory_model} ordering:{step.ordering} parallelism:{step.parallelism} materialization:{step.materialization}")
        lines.append("    alternatives = " + (", ".join(step.alternatives) if step.alternatives else "none"))
    lines.append(f"  segments = {len(plan.segments)}")
    for segment in plan.segments:
        lines.append(f"  segment {segment.index}: mode={segment.mode} execution_mode={segment.execution_mode} levels={','.join(map(str, segment.levels))} nodes={','.join(segment.nodes)}")
        lines.append(f"    transition = entry:{','.join(segment.entry_nodes)} -> exit:{','.join(segment.exit_nodes)}")
        contract = segment.data_contract
        if contract is not None:
            lines.append(
                "    contract = "
                f"inputs:{','.join(contract.inputs) or 'none'} "
                f"outputs:{','.join(contract.outputs) or 'none'} "
                f"state_in:{','.join(contract.state_inputs) or 'none'} "
                f"state_out:{','.join(contract.state_outputs) or 'none'} "
                f"entity_in:{','.join(contract.entity_inputs) or 'none'} "
                f"entity_out:{','.join(contract.entity_outputs) or 'none'} "
                f"data_in:{','.join(contract.data_inputs) or 'none'}"
            )
    rp = plan.record_plan
    if rp is not None:
        lines.append(f"  record_plan = {getattr(rp, 'mode', 'unknown')} cost={getattr(rp, 'estimated_cost', 0):g} boundaries={','.join(getattr(rp, 'materialization_boundaries', ())) or 'none'}")
        lines.append("    segments = " + " | ".join("->".join(seg) for seg in getattr(rp, "fused_segments", ())))
    lines.append(f"  execution_regions = {len(plan.execution_regions)}")
    for region in plan.execution_regions:
        lines.append(f"  execution_region {region.index}: mode={region.mode} levels={','.join(map(str, region.levels))} nodes={','.join(region.nodes)}")
    lines.append(f"  levels = {plan.levels}")
    lines.append(f"  operations = {plan.operation_count}")
    lines.append("  deterministic = yes")
    lines.append("  backend_input = explicit-selected-strategies")
    lines.append("  segmentation = capability-aware-static")
    lines.append("}")
    return "\n".join(lines)

