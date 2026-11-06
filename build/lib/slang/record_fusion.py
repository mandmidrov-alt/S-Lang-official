"""Deterministic planning for schema-changing Record transformation fusion."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RecordFusionDecision:
    chain: tuple[str, ...]
    fused_segments: tuple[tuple[str, ...], ...]
    materialization_boundaries: tuple[str, ...]
    estimated_cost: float
    mode: str  # full | partial | materialized
    reason: str
    downstream_pressure: float = 0.0
    downstream_fanout: int = 0
    # Field-level transfer strategies selected by the global optimizer. Each
    # entry is (endpoint, consumer, field, strategy, cost, source_fields).
    # Keeping this on the authoritative Record decision makes the decision
    # available to downstream backends without recomputing it.
    field_strategies: tuple[tuple[str, str, str, str, float, tuple[str, ...]], ...] = ()
    # Shared field-retention contract for Record fan-out boundaries.
    record_fanout_field_requirements: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # Shared derived-field reuse selected by the global optimizer. Each entry is
    # (endpoint, field, source_fields, independent_cost, shared_cost).
    record_shared_recompute_decisions: tuple[tuple[str, str, tuple[str, ...], float, float], ...] = ()


def _expr_complexity(expr) -> int:
    if expr is None:
        return 1
    name = type(expr).__name__
    if name in {"Literal", "Name"}:
        return 1
    if name in {"Field", "Property"}:
        return 1 + _expr_complexity(getattr(expr, "base", None))
    if name in {"Binary", "Compare", "Logical"}:
        return 1 + _expr_complexity(getattr(expr, "left", None)) + _expr_complexity(getattr(expr, "right", None))
    if name == "Conditional":
        return 1 + sum(_expr_complexity(getattr(expr, x, None)) for x in ("condition", "then_expr", "else_expr"))
    if name == "Call":
        return 2 + sum(_expr_complexity(a) for a in getattr(expr, "args", ()))
    return 2


def _map_complexity(op) -> int:
    expr = getattr(op, "expr", None)
    return max(1, _expr_complexity(expr))


def _safe_record_map(op, schemas) -> bool:
    expr = getattr(op, "expr", None)
    if type(expr).__name__ != "Call":
        return False
    schema = schemas.get(getattr(expr, "name", ""))
    if schema is None:
        return False
    fields = tuple(getattr(schema, "fields", ()))
    return len(fields) == len(getattr(expr, "args", ()))


def enumerate_record_chain_plans(chain_ops, schemas, downstream=None, max_options: int = 256) -> tuple[RecordFusionDecision, ...]:
    """Enumerate deterministic legal fusion/materialization alternatives.

    Every partition of a typed Record chain is a legal structural alternative;
    the global optimizer may choose among them.  The enumeration is bounded so
    long chains cannot explode the planning search space.
    """
    if not chain_ops or not all(_safe_record_map(op, schemas) for op in chain_ops):
        return ()
    downstream = downstream or {}
    names = tuple([chain_ops[0].source] + [op.result for op in chain_ops])
    n = len(chain_ops)
    complexity = [_map_complexity(op) for op in chain_ops]
    out = []
    # A partition is represented by cut positions between transforms.
    import itertools
    cuts_count = min(n - 1, 8)
    for mask in range(1 << cuts_count):
        if n - 1 > cuts_count and mask != (1 << cuts_count) - 1:
            continue
        segments_idx = []
        start = 0
        for cut in range(n - 1):
            if cut < cuts_count and (mask & (1 << cut)):
                segments_idx.append((start, cut + 1))
                start = cut + 1
        segments_idx.append((start, n))
        cost = 0.0
        for seg_i, (a, b) in enumerate(segments_idx):
            accumulated = sum(complexity[a:b])
            length = b - a
            cost += 0.55 * accumulated + 0.18 * (length * length)
            if seg_i > 0:
                cost += 1.5
            endpoint = names[b]
            profile = downstream.get(endpoint, {})
            pressure = float(profile.get("pressure", 0.0))
            fanout = int(profile.get("fanout", 0))
            cost += 0.20 * pressure + 0.90 * max(0, fanout - 1)

            # A fan-out node inside a fused segment has consumers outside the
            # linear Record chain. Keeping that node internal would force the
            # backend to preserve/materialize an otherwise fused intermediate
            # for those external consumers, reducing the benefit of continuing
            # fusion through it. Treat this as a graph-level pressure term.
            # A boundary exactly at the fan-out node is not charged here: that
            # is the alternative that explicitly makes the shared value a
            # stable materialized point.
            internal_names = names[a + 1:b]
            for internal in internal_names:
                internal_profile = downstream.get(internal, {})
                internal_fanout = int(internal_profile.get("external_fanout", 0))
                if internal_fanout > 0:
                    cost += 1.80 * internal_fanout
        fused = tuple(tuple(names[a:b + 1]) for a, b in segments_idx)
        boundaries = tuple(names[a] for a, _ in segments_idx[1:])
        if len(segments_idx) == 1:
            mode = "full"
        elif len(segments_idx) == n:
            mode = "materialized"
        else:
            mode = "partial"
        reason = f"global Record alternative: {mode} ({len(segments_idx)} segment(s))"
        out.append(RecordFusionDecision(names, fused, boundaries, round(cost, 3), mode, reason,
                                        round(sum(float(v.get("pressure", 0.0)) for v in downstream.values()), 3),
                                        sum(int(v.get("fanout", 0)) for v in downstream.values())))
    out.sort(key=lambda d: (d.estimated_cost, d.fused_segments))
    return tuple(out[:max_options])


def plan_record_chain(chain_ops, schemas, downstream=None) -> RecordFusionDecision | None:
    """Choose deterministic fusion/materialization boundaries for one chain.

    The objective is deliberately relative: a fused segment avoids a materialized
    intermediate but accumulates expression/code-size pressure as the segment
    grows. This prevents arbitrarily long chains from being forced into one huge
    generated expression while retaining full fusion for ordinary chains.
    """
    if not chain_ops or not all(_safe_record_map(op, schemas) for op in chain_ops):
        return None
    downstream = downstream or {}
    names = tuple([chain_ops[0].source] + [op.result for op in chain_ops])
    n = len(chain_ops)
    complexity = [_map_complexity(op) for op in chain_ops]

    # dp[i] = (cost, segments), covering the first i transforms.
    dp: list[tuple[float, tuple[tuple[int, int], ...]]] = [(float("inf"), ()) for _ in range(n + 1)]
    dp[0] = (0.0, ())
    for i in range(n):
        base_cost, base_segments = dp[i]
        if base_cost == float("inf"):
            continue
        accumulated = 0
        for j in range(i, n):
            accumulated += complexity[j]
            length = j - i + 1
            # One-pass fusion gets cheaper per operation but pays bounded
            # code-generation pressure for increasingly complex segments.
            segment_cost = 0.55 * accumulated + 0.18 * (length * length)
            if i > 0:
                segment_cost += 1.5  # materialization boundary before segment
            # Include the pressure created by the first consumer after the segment.
            # This is deliberately a relative planning term: sort/reduce/aggregate
            # consumers benefit from a stable materialization boundary, while a
            # simple filter/map consumer benefits more from carrying the fused
            # expression forward. Multiple consumers strongly favor a boundary.
            endpoint = names[j + 1]
            profile = downstream.get(endpoint, {})
            pressure = float(profile.get("pressure", 0.0))
            fanout = int(profile.get("fanout", 0))
            candidate = segment_cost + 0.20 * pressure + 0.90 * max(0, fanout - 1)

            # Penalize fan-out nodes that are internal to this fused segment.
            # Such a node is simultaneously consumed by the next Record
            # transform and by an external branch, so a fully streaming
            # realization cannot keep the intermediate purely ephemeral.
            for internal in names[i + 1:j + 1]:
                internal_profile = downstream.get(internal, {})
                internal_fanout = int(internal_profile.get("external_fanout", 0))
                if internal_fanout > 0:
                    candidate += 1.80 * internal_fanout

            if profile.get("kind") in {"sort", "aggregate", "reduce"} and length > 1:
                candidate += 0.35
            candidate = base_cost + candidate
            if candidate < dp[j + 1][0]:
                dp[j + 1] = (candidate, base_segments + ((i, j + 1),))

    cost, segments = dp[n]
    if not segments:
        return None
    fused = tuple(tuple(names[a:b + 1]) for a, b in segments)
    boundaries = tuple(names[a] for a, b in segments[1:])
    if len(segments) == 1:
        mode = "full"
        reason = "global Record-chain objective selected one fused segment"
    elif len(segments) == n:
        mode = "materialized"
        reason = "global Record-chain objective retained every intermediate boundary"
    else:
        mode = "partial"
        reason = "global Record-chain objective selected fused segments with explicit materialization boundaries"
    total_pressure = round(sum(float(v.get("pressure", 0.0)) for v in downstream.values()), 3)
    total_fanout = sum(int(v.get("fanout", 0)) for v in downstream.values())
    return RecordFusionDecision(names, fused, boundaries, round(cost, 3), mode, reason, total_pressure, total_fanout)



def analyze_record_downstream(program, chain_ops):
    """Build a deterministic downstream profile for Record-chain planning."""
    ast = program.ast
    by_source = {}
    collections = (ast.maps, ast.filters, ast.sorts, ast.aggregates, ast.reduces, ast.conditional_pipelines)
    for collection in collections:
        for op in collection:
            src = getattr(op, "source", None)
            if src is None:
                continue
            kind = type(op).__name__.replace("Op", "").lower()
            weight = {"filter": 1.0, "map": 1.0, "sort": 2.5, "aggregate": 3.0, "reduce": 3.0, "conditional_pipeline": 2.0}.get(kind, 1.5)
            by_source.setdefault(src, []).append((kind, weight))
    profile = {}
    chain_names = {chain_ops[i].result for i in range(len(chain_ops))}
    chain_next = {
        chain_ops[i].result: chain_ops[i + 1].result
        for i in range(len(chain_ops) - 1)
    }
    for name in chain_names:
        consumers = by_source.get(name, [])
        next_name = chain_next.get(name)
        external_consumers = [
            item for item in consumers
            if not (item[0] == "map" and next_name is not None)
        ]
        profile[name] = {
            "kind": consumers[0][0] if len(consumers) == 1 else ("multiple" if len(consumers) else "terminal"),
            "pressure": round(sum(w for _, w in consumers), 3),
            # Keep ``fanout`` as the total direct consumer count for backward
            # compatible diagnostics. ``external_fanout`` is the graph-planning
            # signal used when deciding whether a node can remain internal to a
            # fused linear Record segment.
            "fanout": len(consumers),
            "external_fanout": len(external_consumers),
        }
    return profile

def find_record_chains(maps, schemas):
    """Return maximal typed Record map chains in deterministic source order."""
    by_source = {m.source: m for m in maps}
    by_result = {m.result: m for m in maps}
    chains = []
    for op in sorted(maps, key=lambda m: (m.source, m.result)):
        if not _safe_record_map(op, schemas):
            continue
        if op.source in by_result and _safe_record_map(by_result[op.source], schemas):
            continue
        chain = [op]
        current = op.result
        seen = {op.result}
        while current in by_source:
            nxt = by_source[current]
            if not _safe_record_map(nxt, schemas) or nxt.result in seen:
                break
            chain.append(nxt)
            seen.add(nxt.result)
            current = nxt.result
        if len(chain) >= 2:
            chains.append(tuple(chain))
    return tuple(chains)
