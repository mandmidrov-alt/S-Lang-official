"""Deterministic semantic algorithm selection for S-Lang 0.72.

Candidates are explicit semantic algorithms with legality rules. The cost model
may choose among legal candidates, but cannot invent an algorithm whose
semantic preconditions are not proven by the IR.
"""
from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR
from .execution_plan import ExecutionPlan
from .cost_model import choose_by_cost, resource_profile, materialization_profile
from .runtime_capability import runtime_strategy_supported

@dataclass(frozen=True)
class AlgorithmCandidate:
    strategy: str
    kind: str
    executable: bool = False
    reason: str = ""

@dataclass(frozen=True)
class StrategyChoice:
    node: str
    strategy: str
    reason: str
    executable: bool = False
    alternatives: tuple[str, ...] = ()
    scores: tuple[tuple[str, float], ...] = ()
    profile: str = "generic"
    rejections: tuple[tuple[str, str], ...] = ()
    runtime_supported: bool = True


def algorithm_candidates(node) -> tuple[AlgorithmCandidate, ...]:
    """Return only algorithms whose semantic preconditions are established."""
    kind = node.kind
    out = [AlgorithmCandidate("generic", "fallback", reason="no semantic specialization")]
    if kind == "filter":
        out.append(AlgorithmCandidate("scan-filter", "filter", reason="reference collection scan"))
        if node.parallel_safe:
            out.append(AlgorithmCandidate("parallel-filter", "filter", reason="pure deterministic predicate permits independent elements"))
    elif kind == "map":
        out.append(AlgorithmCandidate("sequential-map", "map", reason="reference element mapping"))
        if node.parallel_safe:
            out.append(AlgorithmCandidate("parallel-map", "map", reason="pure deterministic mapping permits independent elements"))
    elif kind == "sort":
        out.append(AlgorithmCandidate("stable-sort", "sort", reason="deterministic stable ordering"))
        if node.parallel_safe:
            # The semantic contract is explicitly stable; implementation may use
            # parallel partition/sort/merge while preserving equal-key order.
            out.append(AlgorithmCandidate("parallel-stable-sort", "sort", reason="stable parallel sort preserves deterministic equal-key order"))
    elif kind == "aggregate":
        out.append(AlgorithmCandidate("sequential-aggregate", "aggregate", reason="exact source order is preserved"))
    elif kind == "reduce":
        out.append(AlgorithmCandidate("sequential-reduce", "reduce", reason="reassociation is not proven safe"))
    elif kind == "conditional-pipeline":
        out.append(AlgorithmCandidate("conditional-pipeline", "conditional-pipeline", reason="deterministic branch selection with sequential branch semantics"))
    elif kind in {"sequence", "goal:transition"}:
        out.append(AlgorithmCandidate("state-transition", kind, reason="each transition depends on the previous state"))
    elif kind == "goal:select":
        out.append(AlgorithmCandidate("goal-scan-select", "goal:select", reason="reference single-pass selection preserves deterministic tie semantics"))
    elif kind == "goal:path":
        out.append(AlgorithmCandidate("graph-shortest-path", "goal:path", reason="reference shortest-path strategy"))
        hints = set(getattr(node, "optimization_hints", ()))
        if "path-all-bidirectional=true" in hints and "path-nonnegative-costs=true" in hints:
            out.append(AlgorithmCandidate("bidirectional-dijkstra", "goal:path", reason="bidirectional graph with non-negative edge costs permits exact bidirectional Dijkstra"))
        if "path-all-bidirectional=true" in hints and "path-nonnegative-costs=true" in hints and "path-graph-nodes" in " ".join(hints):
            try:
                node_count = int(next(h.split("=", 1)[1] for h in hints if h.startswith("path-graph-nodes=")))
            except (StopIteration, ValueError):
                node_count = 0
            if node_count >= 5:
                out.append(AlgorithmCandidate("a-star-landmark", "goal:path", reason="ALT landmark heuristic is admissible for undirected non-negative graphs"))
    elif kind == "goal:satisfy":
        out.append(AlgorithmCandidate("constraint-propagation", "goal:satisfy", reason="linear bounded integer constraints can be narrowed before exact evaluation"))
        out.append(AlgorithmCandidate("constraint-enumeration", "goal:satisfy", reason="reference finite-domain solver fallback"))
    elif kind == "physics.gravity":
        out.append(AlgorithmCandidate("physics-domain", "physics.gravity", reason="domain-specific semantic operation"))
    elif node.parallel_safe and kind not in {"function", "property"}:
        out.append(AlgorithmCandidate("parallel-generic", "fallback", reason="IR proves reorderable and parallel-safe"))
    return tuple(dict.fromkeys(out))


def _strategy_candidates(node) -> tuple[str, ...]:
    return tuple(c.strategy for c in algorithm_candidates(node))


def select_strategy(
    node,
    fusion_strategies: tuple[str, ...] = (),
    allowed_strategies: tuple[str, ...] | None = None,
    backend_memory_models: tuple[str, ...] | None = None,
    backend_orderings: tuple[str, ...] | None = None,
    backend_parallelism: tuple[str, ...] | None = None,
    backend_materialization: tuple[str, ...] | None = None,
    backend_resource_preferences: tuple[tuple[str, float], ...] | None = None,
) -> StrategyChoice:
    original_candidates = list(_strategy_candidates(node))
    for strategy in fusion_strategies:
        if strategy not in original_candidates:
            original_candidates.append(strategy)
    candidates = list(original_candidates)
    rejection_reasons = {}
    if allowed_strategies is not None:
        allowed = set(allowed_strategies)
        for c in candidates:
            if c not in allowed:
                rejection_reasons[c] = "not allowed by backend strategy set"
        candidates = [c for c in candidates if c in allowed]
    if backend_memory_models is not None or backend_orderings is not None or backend_parallelism is not None or backend_materialization is not None:
        # Only explicitly supplied capability dimensions constrain selection.
        # A backend may, for example, constrain parallelism without implicitly
        # declaring that all other resource models are unsupported.
        memory_ok = set(backend_memory_models) if backend_memory_models is not None else None
        ordering_ok = set(backend_orderings) if backend_orderings is not None else None
        parallel_ok = set(backend_parallelism) if backend_parallelism is not None else None
        materialization_ok = set(backend_materialization) if backend_materialization is not None else None
        filtered = []
        for candidate in candidates:
            memory, ordering, parallelism = resource_profile(candidate)
            materialization = materialization_profile(candidate)
            reasons = []
            if memory_ok is not None and memory != "abstract" and memory not in memory_ok:
                reasons.append(f"memory={memory} unsupported")
            if ordering_ok is not None and ordering not in ordering_ok:
                reasons.append(f"ordering={ordering} unsupported")
            if parallel_ok is not None and parallelism not in parallel_ok:
                reasons.append(f"parallelism={parallelism} unsupported")
            if materialization_ok is not None and materialization not in materialization_ok:
                reasons.append(f"materialization={materialization} unsupported")
            if reasons:
                rejection_reasons[candidate] = "; ".join(reasons)
                continue
            filtered.append(candidate)
        candidates = filtered
    runtime_rejected = {}
    runtime_candidates = [c for c in candidates if runtime_strategy_supported(node.kind, c)]
    for c in candidates:
        if c not in runtime_candidates:
            runtime_rejected[c] = f"strategy '{c}' is semantically legal but has no unified runtime contract"
    # Prefer executable strategies whenever one exists.  If none exists, keep
    # the semantic candidates: the selected plan remains valid and the
    # capability audit will explicitly mark the node as reference fallback.
    selection_candidates = runtime_candidates or candidates
    if not selection_candidates:
        raise ValueError(f"no backend-supported strategy for node {node.binding}")
    decision = choose_by_cost(node, tuple(selection_candidates), backend_resource_preferences)
    all_candidates = algorithm_candidates(node)
    selected = next((c for c in all_candidates if c.strategy == decision.selected), None)
    if selected is None and decision.selected.startswith("fused-"):
        selected = AlgorithmCandidate(decision.selected, node.kind, reason="ExecutionPlan proved a legal fusion group")
    if selected is None:
        selected = next((c for c in all_candidates if c.strategy in candidates), AlgorithmCandidate(candidates[0], node.kind, reason="backend-supported fallback"))
    def profile(strategy: str) -> str:
        if strategy.startswith("fused-"):
            return "fused"
        if strategy.startswith("parallel-"):
            return "parallel"
        if strategy in {"scan-filter", "sequential-map", "sequential-aggregate", "sequential-reduce", "state-transition"}:
            return "sequential"
        if strategy in {"stable-sort", "goal-scan-select", "graph-shortest-path", "bidirectional-dijkstra", "a-star-landmark", "constraint-propagation", "constraint-enumeration", "physics-domain"}:
            return "specialized"
        return "generic"

    ranked = choose_by_cost(node, tuple(selection_candidates), backend_resource_preferences).estimates
    combined_rejections = dict(rejection_reasons)
    combined_rejections.update(runtime_rejected)
    selected_runtime_supported = runtime_strategy_supported(node.kind, selected.strategy)
    reason = f"cost model selected from {', '.join(_strategy_candidates(node))}: {selected.reason}"
    if selected_runtime_supported:
        reason += "; unified runtime contract available"
    else:
        reason += "; semantically legal but requires reference-interpreter fallback"
    return StrategyChoice(
        node.binding, selected.strategy,
        reason,
        selected.executable,
        alternatives=tuple(e.strategy for e in ranked),
        scores=tuple((e.strategy, e.score) for e in ranked),
        profile=profile(selected.strategy),
        rejections=tuple((name, combined_rejections[name]) for name in original_candidates if name in combined_rejections),
        runtime_supported=selected_runtime_supported,
    )


def build_strategy_choices(
    plan: ExecutionPlan,
    ir: ExecutionIR,
    allowed_strategies: tuple[str, ...] | None = None,
    backend_memory_models: tuple[str, ...] | None = None,
    backend_orderings: tuple[str, ...] | None = None,
    backend_parallelism: tuple[str, ...] | None = None,
    backend_materialization: tuple[str, ...] | None = None,
    backend_resource_preferences: tuple[tuple[str, float], ...] | None = None,
) -> tuple[StrategyChoice, ...]:
    by = ir.by_binding()
    fused_by_node = {}
    for group in plan.fusion_groups:
        fused_by_node.setdefault(group.terminal, []).append(group.strategy)
    choices = []
    for step in plan.steps:
        for name in step.nodes:
            choices.append(select_strategy(by[name], tuple(fused_by_node.get(name, ())), allowed_strategies, backend_memory_models, backend_orderings, backend_parallelism, backend_materialization, backend_resource_preferences))
    return tuple(choices)


def format_strategy_choices(choices: tuple[StrategyChoice, ...]) -> str:
    lines = ["strategy.selection {"]
    for c in choices:
        lines.append(f"  {c.node}: {c.strategy} profile={c.profile} ({c.reason})")
        if c.alternatives:
            lines.append("    alternatives = " + ", ".join(c.alternatives))
        if c.scores:
            lines.append("    scores = " + ", ".join(f"{name}:{score:g}" for name, score in c.scores))
    lines += [
        f"  choices = {len(choices)}",
        "  selection_model = cost-and-resource-aware-static-algorithm-selection",
        "  runtime_measurements = not-used",
        "  backend_execution = selected-strategy-aware-native-backend",
        "  selection = deterministic",
        "}",
    ]
    return "\n".join(lines)


def cost_analysis(plan: ExecutionPlan, ir: ExecutionIR) -> str:
    from .cost_model import format_cost_decision
    by = ir.by_binding()
    lines = ["cost.analysis {"]
    for step in plan.steps:
        for name in step.nodes:
            node = by[name]
            fusion = tuple(g.strategy for g in plan.fusion_groups if name in g.nodes)
            candidates = tuple(dict.fromkeys(_strategy_candidates(node) + fusion))
            decision = choose_by_cost(node, candidates)
            lines.append(format_cost_decision(decision))
    lines += [
        "  model = static-relative",
        "  algorithm_candidates = semantically-legal-only",
        "  runtime_measurements = not-used",
        "  cardinality = per-node compile-time estimate",
        "}",
    ]
    return "\n".join(lines)
