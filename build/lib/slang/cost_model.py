"""Deterministic static cost model for S-Lang 0.71.

The model is deliberately relative rather than hardware-calibrated.  When
compile-time data-shape bounds are available it scales work by the relevant
algorithmic complexity and uses conservative lower bounds for strategy
selection.  Unknown sizes fall back to the fixed reference model.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class CostEstimate:
    strategy: str
    work: float
    overhead: float
    parallelism: float
    score: float
    reason: str
    work_lower: float | None = None
    work_upper: float | None = None
    cardinality: str = "unknown"
    complexity: str = "linear"
    memory: str = "abstract"
    ordering: str = "source-order"
    parallelism_mode: str = "sequential"

@dataclass(frozen=True)
class CostDecision:
    node: str
    selected: str
    estimates: tuple[CostEstimate, ...]
    confidence: str

_BASE_WORK = {
    "filter": 10.0, "map": 10.0, "sort": 25.0, "aggregate": 12.0,
    "reduce": 12.0, "sequence": 12.0, "goal:select": 14.0,
    "goal:path": 30.0, "goal:satisfy": 35.0, "physics.gravity": 30.0, "conditional-pipeline": 18.0,
}
_SPECIALIZED = {
    "filter", "map", "sort", "aggregate", "reduce", "sequence",
    "goal:select", "goal:path", "goal:satisfy", "physics.gravity", "conditional-pipeline",
}

def _shape(node):
    return getattr(node, "data_shape", None)

def _complexity(node):
    shape = _shape(node)
    return getattr(shape, "complexity", "linear") if shape is not None else "linear"

def _complexity_factor(n: int, complexity: str) -> float:
    n = max(1, int(n))
    if complexity == "constant":
        return 1.0
    if complexity == "nlogn":
        # Normalize so n=10 has factor 1.0, while retaining n log n growth.
        return max(0.1, (n * max(1.0, math.log2(max(2, n)))) / (10.0 * math.log2(10)))
    # Constraint and graph searches are currently represented by their known
    # search/result cardinality. More detailed graph/domain costs are future work.
    return max(0.1, n / 10.0)

def _hint_number(node, prefix: str) -> float | None:
    for hint in getattr(node, "optimization_hints", ()):
        if hint.startswith(prefix + "="):
            try:
                return float(hint.split("=", 1)[1])
            except ValueError:
                return None
    return None

def _work_bounds(node) -> tuple[float, float, str, str]:
    base = _BASE_WORK.get(node.kind, 8.0) + 2.0 * len(node.dependencies) + 1.0 * len(node.external_sources)
    if node.kind == "goal:path":
        edges = _hint_number(node, "path-graph-edges")
        vertices = _hint_number(node, "path-graph-nodes")
        if edges is not None:
            # Shortest-path work is driven by graph size, not by the single
            # path value returned to the next stage. This is a relative static
            # model, not a runtime benchmark.
            graph_work = max(1.0, edges + (vertices or 0.0))
            return base * _complexity_factor(int(graph_work), "linear"), base * _complexity_factor(int(graph_work), "linear"), "derived", "graph-search"
    shape = _shape(node)
    complexity = _complexity(node)
    if shape is None or shape.upper is None:
        return base, base, "unknown", complexity
    # Preserve explicit cardinality overrides used by downstream planners and
    # tests that construct a modified ExecutionNode from an existing shape.
    explicit = getattr(node, "cardinality", None)
    explicit_conf = getattr(node, "cardinality_confidence", "unknown")
    if explicit is not None and explicit_conf == "exact" and shape.cardinality != explicit:
        lower = upper = explicit
        return base * _complexity_factor(lower, complexity), base * _complexity_factor(upper, complexity), "exact", complexity
    lower = shape.lower if shape.lower is not None else 0
    upper = shape.upper
    # A bounded shape is selected conservatively: only work guaranteed by the
    # lower bound is used to justify parallel overhead amortization.
    return base * _complexity_factor(lower, complexity), base * _complexity_factor(upper, complexity), ("exact" if shape.exact else "bounded"), complexity

def _work(node) -> float:
    """Backward-compatible scalar work estimate used by older callers/tests."""
    lo, hi, confidence, _ = _work_bounds(node)
    if confidence == "exact":
        return lo
    if confidence == "bounded":
        return lo
    return lo

def _cardinality_note(node):
    shape = _shape(node)
    if shape is None or shape.upper is None:
        return "cardinality unknown; conservative base estimate"
    if shape.exact:
        return f"cardinality={shape.lower} exact"
    return f"cardinality bounds=[{shape.lower},{shape.upper}] bounded; conservative lower-bound selection"

def resource_profile(strategy: str) -> tuple[str, str, str]:
    """Return (memory model, ordering, parallelism) required by a strategy."""
    if strategy in {"scan-filter", "sequential-map", "sequential-aggregate", "sequential-reduce", "conditional-pipeline"}:
        memory = "linear-buffer" if strategy in {"scan-filter", "sequential-map"} else "scalar-accumulator"
        return memory, "source-order", "sequential"
    if strategy in {"parallel-filter", "parallel-map", "parallel-stable-sort", "parallel-generic"}:
        memory = "linear-buffer"
        return memory, "dependency-ordered", "parallel-where-independent"
    if strategy in {"fused-filter-map-reduce", "fused-filter-map-aggregate"}:
        return "scalar-accumulator", "source-order", "sequential"
    if strategy in {"stable-sort", "collection-sort"}:
        return "linear-buffer", "source-order", "sequential"
    if strategy in {"collection-filter", "collection-map", "collection-aggregate", "collection-reduce", "sequence-engine"}:
        return "linear-buffer", "source-order", "sequential"
    return "abstract", "source-order", "sequential"

def materialization_profile(strategy: str) -> str:
    """Return the materialization contract required by a strategy."""
    if strategy.startswith("fused-"):
        return "streaming-when-fused"
    return "backend-defined"


def _candidate_cost(node, strategy):
    lower, upper, confidence, complexity = _work_bounds(node)
    if strategy == "parallel-stable-sort":
        parallelism, overhead = 4.0, 7.0
        score = overhead + lower / parallelism
        reason = f"{_cardinality_note(node)}; stable parallel sort amortizes partition/merge overhead"
    elif strategy.startswith("parallel-"):
        parallelism, overhead = 4.0, 4.0
        score = overhead + lower / parallelism
        reason = f"{_cardinality_note(node)}; parallel overhead amortized against guaranteed work"
    elif strategy == "parallel-generic":
        parallelism, overhead = 4.0, 5.0
        score = overhead + lower / parallelism
        reason = f"{_cardinality_note(node)}; generic parallel execution is permitted by IR properties"
    elif strategy == "generic":
        parallelism, overhead, score = 1.0, 3.0, lower + 3.0
        reason = "generic fallback has no semantic specialization"
    elif strategy.startswith("fused-") and "-then-" in strategy:
        parallelism, overhead = 1.0, 2.0
        score = max(0.1, lower * 0.82) + overhead
        reason = f"{_cardinality_note(node)}; partial fusion removes some intermediate materialization but retains a boundary"
    elif strategy.startswith("fused-"):
        parallelism, overhead = 1.0, 1.0
        score = max(0.1, lower * 0.70) + overhead
        reason = f"{_cardinality_note(node)}; one-pass fusion removes intermediate collection materialization"
    elif strategy in {"scan-filter", "sequential-map", "sequential-aggregate", "sequential-reduce", "state-transition", "conditional-pipeline"}:
        parallelism, overhead, score = 1.0, 0.0, lower
        reason = f"{_cardinality_note(node)}; sequential reference cost"
    elif strategy in {"stable-sort", "collection-sort", "collection-filter", "collection-map", "collection-aggregate", "sequence-engine"}:
        parallelism, overhead, score = 1.0, 1.0, lower + 1.0
        reason = "specialized deterministic backend candidate"
    elif strategy == "constraint-propagation":
        parallelism, overhead = 1.0, 0.5
        # Propagation is a preprocessing pass whose cost is small relative to
        # enumeration.  Its main benefit is the reduced search space.
        score = max(0.5, lower * 0.12) + overhead
        reason = f"{_cardinality_note(node)}; interval propagation reduces finite-domain search before exact evaluation"
    elif strategy == "bidirectional-dijkstra":
        parallelism, overhead = 1.0, 0.8
        score = max(1.0, lower * 0.68) + overhead
        reason = f"{_cardinality_note(node)}; exact bidirectional search reduces frontier growth on eligible graphs"
    elif strategy == "a-star-landmark":
        parallelism, overhead = 1.0, 1.2
        # ALT performs one deterministic landmark preprocessing search and then
        # uses an admissible lower bound during A*. Keep preprocessing visible
        # in the static score so A* is not treated as free.
        score = max(1.0, lower * 0.52) + overhead
        reason = f"{_cardinality_note(node)}; admissible landmark heuristic reduces explored frontier after preprocessing"
    elif strategy in {"goal-scan-select", "graph-shortest-path", "constraint-enumeration", "goal-selection", "graph-search", "constraint-solver", "physics-domain", "physics-backend"}:
        parallelism, overhead, score = 1.0, 1.0, lower + 1.0
        reason = "reference semantic-domain strategy"
    else:
        parallelism, overhead, score = 1.0, 1.0, lower + 1.0
        reason = "conservative fallback estimate"
    memory, ordering, parallel_mode = resource_profile(strategy)
    # Resource-aware penalties remain relative and deterministic. They are not
    # hardware measurements; they encode semantic resource pressure so a
    # streaming/fused plan is preferred when it is otherwise comparable.
    shape = _shape(node)
    if memory == "linear-buffer" and shape is not None and shape.upper is not None:
        score += min(12.0, max(0.0, shape.upper) / 1000.0)
        reason += "; buffer-memory pressure included"
    if parallel_mode == "parallel-where-independent":
        score += 0.5
        reason += "; parallel coordination cost included"
    return CostEstimate(
        strategy, round(lower, 3), overhead, parallelism, round(score, 3), reason,
        round(lower, 3), round(upper, 3), confidence, complexity, memory, ordering, parallel_mode,
    )

def rank_candidates(node, candidates):
    return tuple(sorted((_candidate_cost(node, c) for c in candidates), key=lambda x: (x.score, x.strategy)))

def _resource_preference_penalty(estimate: CostEstimate, preferences=None) -> float:
    """Apply backend-declared resource priorities without changing legality.

    Preferences are weights, not measurements: a larger value means that the
    backend cares more about avoiding the corresponding resource pressure.
    """
    prefs = dict(preferences or ())
    pressure = {
        "memory": {"abstract": 0.0, "scalar-accumulator": 0.25, "linear-buffer": 1.0, "memref": 1.0}.get(estimate.memory, 1.0),
        "ordering": {"source-order": 0.0, "dependency-ordered": 0.25}.get(estimate.ordering, 0.25),
        "parallelism": {"sequential": 0.0, "parallel-where-independent": 0.5}.get(estimate.parallelism_mode, 0.25),
        "materialization": 0.0 if estimate.strategy.startswith("fused-") else 0.1,
    }
    score = sum(float(prefs.get(name, 0.0)) * value for name, value in pressure.items())
    # More available cores reduce the relative cost of an already-legal
    # parallel strategy. This is a bounded deterministic preference, not a
    # runtime benchmark, so the compiler remains reproducible.
    if estimate.parallelism_mode == "parallel-where-independent":
        cores = max(1.0, float(prefs.get("cpu_cores", 1.0)))
        if cores > 1.0:
            score -= min(1.0, 0.25 * math.log2(cores))
    return score

def choose_by_cost(node, candidates, resource_preferences=None):
    estimates = tuple(
        CostEstimate(
            e.strategy, e.work, e.overhead, e.parallelism,
            round(e.score + _resource_preference_penalty(e, resource_preferences), 3),
            e.reason + ("; backend resource preferences applied" if resource_preferences else ""),
            e.work_lower, e.work_upper, e.cardinality, e.complexity,
            e.memory, e.ordering, e.parallelism_mode,
        )
        for e in rank_candidates(node, candidates)
    )
    estimates = tuple(sorted(estimates, key=lambda x: (x.score, x.strategy)))
    confidence = getattr(node, "cardinality_confidence", "unknown") if estimates else "none"
    return CostDecision(node.binding, estimates[0].strategy if estimates else "generic", estimates, confidence)

def format_cost_decision(decision):
    lines = [f"  {decision.node}: selected={decision.selected} confidence={decision.confidence}"]
    for e in decision.estimates:
        bounds = ""
        if e.work_lower is not None and e.work_upper is not None:
            bounds = f" work_bounds=[{e.work_lower:g},{e.work_upper:g}]"
        lines.append(
            f"    {e.strategy}: work={e.work:g}{bounds} complexity={e.complexity} memory={e.memory} ordering={e.ordering} "
            f"parallel_mode={e.parallelism_mode} overhead={e.overhead:g} parallelism={e.parallelism:g} score={e.score:g} ({e.reason})"
        )
    return "\n".join(lines)
