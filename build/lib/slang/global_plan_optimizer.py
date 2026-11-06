"""Global static optimization of the selected S-Lang execution chain.

The optimizer evaluates the whole dependency graph rather than treating each
node as an isolated operation. It never introduces a new algorithm: it only
chooses among strategies already proven legal by the local strategy planner.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from .strategy_selection import StrategyChoice
from .cost_model import materialization_profile, resource_profile


@dataclass(frozen=True)
class GlobalPlanCost:
    local_cost: float
    boundary_cost: float
    chain_cost: float
    total_cost: float
    materialization_boundaries: int
    fused_internal_edges: int
    strategy_transitions: int
    cardinality_weighted_cost: float
    estimated_peak_cardinality: int | None
    selectivity_weighted_cost: float
    estimated_selectivities: tuple[tuple[str, float], ...]
    downstream_pressure: tuple[tuple[str, float], ...]
    strategy_context_cost: float
    search_mode: str = "exhaustive"
    strategy_combinations_evaluated: int = 1
    strategy_search_space: int = 1
    global_optimality: str = "exhaustive"
    profile_transition_cost: float = 0.0
    parallel_islands: int = 0
    materialization_reuse_cost: float = 0.0
    peak_live_cardinality: int | None = None
    profile_signature: tuple[tuple[str, str, str, str], ...] = ()
    execution_region_cost: float = 0.0
    execution_regions: tuple[tuple[str, int, int], ...] = ()
    record_fusion_cost: float = 0.0
    record_fusion_fusions: int = 0
    record_fusion_partial: int = 0
    record_fusion_materialized: int = 0
    record_downstream_cost: float = 0.0
    record_downstream_fanout: int = 0
    record_downstream_consumers: tuple[tuple[str, str, float], ...] = ()
    record_schema_width: float = 0.0
    record_schema_complexity: float = 1.0
    record_materialization_cost: float = 0.0
    record_projected_fields: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    record_projection_savings: float = 0.0
    record_plan_mode: str = "none"
    record_plan_alternatives: int = 1
    record_plan: object | None = None
    record_materialization_strategies: tuple[tuple[str, str, float, tuple[str, ...]], ...] = ()
    record_recompute_cost: float = 0.0
    record_partial_recompute_cost: float = 0.0
    record_recompute_provenance: tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...], str], ...]], ...] = ()
    record_field_strategies: tuple[tuple[str, str, str, str, float, tuple[str, ...]], ...] = ()
    # Global fan-out contract: fields that must survive the shared Record
    # materialization boundary for all downstream consumers combined.
    record_fanout_field_requirements: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # Shared derived-field reuse across multiple downstream branches.
    record_shared_recompute_savings: float = 0.0
    record_shared_recompute_decisions: tuple[tuple[str, str, tuple[str, ...], float, float], ...] = ()


def _score(choice: StrategyChoice, strategy: str) -> float:
    return next((float(s) for name, s in choice.scores if name == strategy), 0.0)


def _is_fused(strategy: str) -> bool:
    return strategy.startswith("fused-")


def _transition_cost(parent_strategy: str, child_strategy: str, parent_kind: str, child_kind: str) -> float:
    """Relative cost of crossing a non-fused semantic stage boundary.

    The model includes both semantic hand-off cost and a small deterministic
    resource-profile compatibility term. The latter is what allows the global
    optimizer to distinguish otherwise similar local strategies based on their
    position in the complete execution graph. These are planning penalties, not
    hardware benchmarks.
    """
    if parent_strategy == child_strategy:
        return 0.0
    goal_parent = parent_kind.startswith("goal:") or parent_kind == "sequence"
    goal_child = child_kind.startswith("goal:") or child_kind == "sequence"
    if goal_parent and goal_child:
        base = 0.75
    elif goal_parent or goal_child:
        base = 0.5
    else:
        base = 0.15

    pmem, porder, pparallel = resource_profile(parent_strategy)
    cmem, corder, cparallel = resource_profile(child_strategy)
    compatibility = 0.0
    if pparallel != cparallel:
        # Crossing the sequential/parallel boundary requires coordination.
        compatibility += 0.15 if pparallel == "parallel-where-independent" else 0.10
    if pmem != cmem and pmem != "abstract" and cmem != "abstract":
        compatibility += 0.05
    if porder != corder:
        compatibility += 0.05
    return base + compatibility


def _hint_selectivity(node) -> float | None:
    for hint in getattr(node, "optimization_hints", ()):
        if hint.startswith(("filter-selectivity=", "goal-selectivity=", "satisfy-search-selectivity=")):
            try:
                return max(0.0, min(1.0, float(hint.split("=", 1)[1])))
            except ValueError:
                return None
    return None


def _selectivity(node) -> float:
    """Return a deterministic selectivity estimate.

    Exact interval-derived hints override the generic heuristic. The result is
    still a compile-time estimate and never changes program semantics.
    """
    kind = node.kind
    hinted = _hint_selectivity(node)
    if hinted is not None:
        return hinted
    if kind in {"filter", "goal:select", "goal:satisfy", "goal:path"}:
        if hinted is not None:
            return hinted
        return 0.5 if kind == "filter" else (0.25 if kind == "goal:select" else (1.0 if kind == "goal:satisfy" else 1.0))
    if kind == "choose":
        return 1.0
    if kind in {"map", "sort", "sequence", "conditional-pipeline"}:
        return 1.0
    if kind in {"aggregate", "reduce"}:
        return 1.0
    if kind.startswith("goal:"):
        return 1.0
    return 1.0


def _effective_cardinalities(ir):
    by = ir.by_binding()
    memo = {}

    def estimate(name, active=()):
        if name in memo:
            return memo[name]
        node = by.get(name)
        if node is None or name in active:
            return 10.0
        if node.cardinality is not None:
            value = float(max(0, node.cardinality))
            if node.kind == "goal:satisfy":
                # Satisfy cardinality is the finite search-space size.
                # Constraint-derived search selectivity estimates the part
                # remaining after sound interval propagation.
                value *= _selectivity(node)
        elif node.data_shape is not None and node.data_shape.upper is not None and node.data_shape.lower == node.data_shape.upper:
            value = float(max(0, node.data_shape.upper))
        elif node.dependencies:
            source = max((estimate(d, active + (name,)) for d in node.dependencies), default=10.0)
            value = source * _selectivity(node)
            if node.kind in {"aggregate", "reduce", "choose", "goal:select"}:
                value = min(value, 1.0)
        else:
            value = 10.0 * _selectivity(node)
        memo[name] = max(0.0, value)
        return memo[name]

    for node in ir.nodes:
        estimate(node.binding)
    return memo


def _downstream_pressure(edges, effective_cards):
    """Estimate how much downstream work depends on each node.

    This is a deterministic planning signal, not a runtime measurement. A
    direct consumer contributes its effective cardinality; transitive
    consumers contribute a discounted amount so long chains do not dominate
    the model without bound.
    """
    children = {}
    for edge in edges:
        children.setdefault(edge.before, []).append(edge.after)
    memo = {}
    def pressure(name, active=()):
        if name in memo:
            return memo[name]
        if name in active:
            return 0.0
        total = 0.0
        for child in children.get(name, ()):
            card = effective_cards.get(child, 10.0)
            total += min(100.0, max(1.0, card))
            total += 0.5 * pressure(child, active + (name,))
        memo[name] = min(500.0, total)
        return memo[name]
    for name in set(children) | {e.after for e in edges}:
        pressure(name)
    return memo


def _profile_signature(selected, ir):
    """Return the deterministic execution-profile signature of the whole graph.

    A profile is the tuple of (binding, memory model, ordering contract,
    parallelism mode) for each node in topological order.  It is deliberately
    semantic: no hardware facts are inferred from it.
    """
    by_ir = ir.by_binding()
    try:
        order = ir.topological_order()
    except Exception:
        order = tuple(n.binding for n in ir.nodes)
    out = []
    for binding in order:
        strategy = selected.get(binding)
        if strategy is None:
            continue
        memory, ordering, parallelism = resource_profile(strategy)
        out.append((binding, memory, ordering, parallelism))
    return tuple(out)


def _execution_region_modes(selected, edges, ir):
    """Derive deterministic execution modes for connected graph regions.

    Modes are semantic planning contracts: streaming, materialized, or
    parallel. A region may contain different node strategies, but a mixed
    region pays a bounded coordination penalty. This makes whole-region mode
    selection explicit instead of treating profile transitions as unrelated
    pairwise events.
    """
    profile = _profile_signature(selected, ir)
    by_node = {b: (m, o, p) for b, m, o, p in profile}
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge.before, set()).add(edge.after)
        adjacency.setdefault(edge.after, set()).add(edge.before)
    nodes = set(by_node)
    regions = []
    seen = set()
    for start in sorted(nodes):
        if start in seen:
            continue
        stack = [start]; seen.add(start); component = []
        while stack:
            cur = stack.pop(); component.append(cur)
            for nxt in sorted(adjacency.get(cur, ())):
                if nxt in nodes and nxt not in seen:
                    seen.add(nxt); stack.append(nxt)
        counts = {"streaming": 0, "materialized": 0, "parallel": 0}
        for node in component:
            memory, ordering, parallelism = by_node[node]
            if parallelism == "parallel-where-independent":
                mode = "parallel"
            elif materialization_profile(selected.get(node, "")) == "streaming-when-fused":
                mode = "streaming"
            else:
                mode = "materialized"
            counts[mode] += 1
        # Deterministic dominant mode; ties use the semantic order below.
        mode = max(("parallel", "streaming", "materialized"),
                   key=lambda m: (counts[m], - ("parallel", "streaming", "materialized").index(m)))
        mixed = sum(1 for value in counts.values() if value) > 1
        regions.append((mode, len(component), int(mixed)))
    # A region with no dependency edges is still a valid independent region.
    return tuple(regions)


def _profile_global_cost(selected, edges, ir, effective_cards):
    """Model whole-graph profile behavior beyond pairwise transitions.

    The model captures four bounded effects:
      * profile transitions across the dependency graph;
      * contiguous parallel regions (parallel islands);
      * materialization pressure when one result is reused by multiple consumers;
      * peak live cardinality in a topological schedule.

    These are deterministic relative planning terms. They are not runtime
    measurements and never alter semantic legality.
    """
    by_ir = ir.by_binding()
    by_result = {str(getattr(n, "result", "")): n for n in ir.nodes if getattr(n, "result", None) is not None}
    children = {}
    for edge in edges:
        children.setdefault(edge.before, []).append(edge.after)

    profile = _profile_signature(selected, ir)
    profile_by_node = {binding: (memory, ordering, parallelism)
                       for binding, memory, ordering, parallelism in profile}

    transition_cost = 0.0
    for edge in edges:
        a = profile_by_node.get(edge.before)
        b = profile_by_node.get(edge.after)
        if not a or not b:
            continue
        if a == b:
            continue
        # Whole-graph profile transitions are intentionally smaller than the
        # primary semantic transition cost. They reward coherent regions
        # without overwhelming algorithmic costs.
        penalty = 0.05
        if a[2] != b[2]:
            penalty += 0.08
        if a[0] != b[0] and a[0] != "abstract" and b[0] != "abstract":
            penalty += 0.04
        if a[1] != b[1]:
            penalty += 0.03
        transition_cost += penalty

    # Count connected parallel regions in the dependency graph. Multiple
    # disconnected parallel islands require separate coordination phases.
    parallel_nodes = {n for n, profile_item in profile_by_node.items()
                      if profile_item[2] == "parallel-where-independent"}
    parallel_components = 0
    seen = set()
    undirected = {}
    for edge in edges:
        undirected.setdefault(edge.before, set()).add(edge.after)
        undirected.setdefault(edge.after, set()).add(edge.before)
    for node in sorted(parallel_nodes):
        if node in seen:
            continue
        parallel_components += 1
        stack = [node]
        seen.add(node)
        while stack:
            current = stack.pop()
            for nxt in undirected.get(current, ()):
                if nxt in parallel_nodes and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)

    # Reuse pressure: a materialized result can be consumed more than once.
    # Penalize repeated materialization, but only when the selected strategy
    # does not provide the fused streaming contract.
    reuse_cost = 0.0
    for parent, consumers in children.items():
        fanout = len(consumers)
        if fanout <= 1:
            continue
        strategy = selected.get(parent, "")
        if materialization_profile(strategy) == "streaming-when-fused":
            continue
        card = min(100.0, max(1.0, effective_cards.get(parent, 10.0)))
        reuse_cost += 0.02 * (fanout - 1) * (1.0 + card / 100.0)

    # Liveness estimate: at each topological point, count cardinalities of
    # values whose last consumer has not yet executed. This is a conservative
    # semantic planning estimate rather than an allocator simulation.
    try:
        order = ir.topological_order()
    except Exception:
        order = tuple(n.binding for n in ir.nodes)
    position = {name: i for i, name in enumerate(order)}
    last_use = {}
    for parent, consumers in children.items():
        if consumers:
            last_use[parent] = max(position.get(c, position.get(parent, 0)) for c in consumers)
        else:
            last_use[parent] = position.get(parent, 0)
    live = 0.0
    peak = 0.0
    for i, name in enumerate(order):
        live += effective_cards.get(name, 10.0)
        for candidate, last in last_use.items():
            if last == i and candidate != name:
                live -= effective_cards.get(candidate, 10.0)
        peak = max(peak, live)
    return (round(transition_cost, 3), parallel_components, round(reuse_cost, 3),
            int(max(0.0, peak)), profile)




def _record_field_weight(type_name, seen=()):
    """Return a deterministic relative storage/copy weight for one field type.

    These are planning units, not byte sizes. They intentionally distinguish
    cheap scalar fields from text, collections, and nested records without
    pretending to know a target machine's allocator or ABI.
    """
    name = str(type_name or "Unknown")
    if name in {"Number", "Float", "Integer"}:
        return 1.0
    if name in {"Boolean", "Bool"}:
        return 0.75
    if name == "Text":
        return 2.0
    if name.startswith("List") or name.startswith("Set"):
        return 3.0
    if name.startswith("Map") or name.startswith("Dictionary"):
        return 3.5
    return 2.5


def _record_schema_profile(node):
    """Estimate record width and structural copy complexity from its schema."""
    schema = getattr(node, "output_schema", None) if node is not None else None
    fields = tuple(getattr(schema, "fields", ()) or ()) if schema is not None else ()
    if not fields:
        return 0.0, 1.0, 0
    width = sum(_record_field_weight(getattr(field, "type_name", None) or getattr(getattr(field, "type", None), "name", None)) for field in fields)
    # A wide schema increases copy/materialization work; nested/non-scalar fields
    # receive a structural surcharge through their larger field weights.
    complexity = 1.0 + min(2.5, max(0, len(fields) - 2) * 0.08)
    complex_fields = sum(1 for field in fields if _record_field_weight(getattr(field, "type_name", None) or getattr(getattr(field, "type", None), "name", None)) > 1.0)
    complexity += min(1.5, complex_fields * 0.06)
    return round(width, 3), round(complexity, 3), len(fields)

def _record_consumer_projection(parent_node, child_node):
    """Return fields of a Record actually touched by one downstream consumer.

    ExecutionIR already records symbolic collection regions such as
    ``source[*].field`` and ``source[*]``. Reusing those regions keeps this
    planning decision independent of AST details and makes the projection
    signal available to every backend. An unqualified row access is treated as
    a full-record consumer because the consumer may inspect any field.
    """
    schema = getattr(parent_node, "output_schema", None) if parent_node is not None else None
    fields = tuple(getattr(schema, "fields", ()) or ()) if schema is not None else ()
    names = tuple(str(getattr(f, "name", "")) for f in fields if getattr(f, "name", None))
    if not names:
        return (), False, 0.0
    regions = tuple(getattr(child_node, "memory_region_specs", ()) or ()) if child_node is not None else ()
    touched = set()
    full = False
    for region in regions:
        selector = getattr(region, "selector", None)
        path = tuple(getattr(region, "path", ()) or ())
        scope = getattr(region, "scope", None)
        if selector == "*" and not path:
            full = True
            break
        if selector == "*" and path:
            field = path[0]
            if field in names:
                touched.add(field)
        elif scope in {"root", "collection", "element"} and not path:
            full = True
            break
    if full or not touched:
        return names, True, 0.0
    # Savings are normalized planning units: fields not needed by the consumer
    # need not participate in a projected materialized hand-off.
    weights = {
        str(getattr(f, "name", "")): _record_field_weight(
            getattr(f, "type_name", None) or getattr(getattr(f, "type", None), "name", None)
        ) for f in fields
    }
    total_weight = sum(weights.values()) or float(len(names))
    used_weight = sum(weights.get(name, 0.0) for name in touched)
    savings = max(0.0, min(0.85, 1.0 - used_weight / total_weight))
    return tuple(sorted(touched)), False, round(savings, 3)


def _record_partial_recompute_candidate(parent_node, child_node, used_fields):
    """Price preserving source fields and recomputing derived outputs later.

    This is distinct from ordinary ``recompute``: instead of carrying the
    derived output field, the plan carries only the root source fields needed
    to reconstruct it at the downstream map. It is legal only for known
    derived provenance and pure/deterministic map consumers. The result is a
    bounded planning estimate, not a backend lowering instruction.
    """
    if parent_node is None or child_node is None or not used_fields:
        return False, 0.0, ()
    if getattr(child_node, "kind", None) != "map":
        return False, 0.0, ()
    if not getattr(child_node, "pure", False) or not getattr(child_node, "deterministic", True):
        return False, 0.0, ()
    provenance = dict((name, (sources, certainty)) for name, sources, certainty
                      in getattr(parent_node, 'record_field_provenance', ()) or ())
    schema = getattr(parent_node, 'output_schema', None)
    fields = {str(getattr(f, 'name', '')): f for f in (getattr(schema, 'fields', ()) or ())}
    evidence = []
    total_source_weight = 0.0
    output_weight = 0.0
    expression_complexity = 0.0
    for name in used_fields:
        item = provenance.get(name)
        if item is None:
            return False, 0.0, ()
        sources, certainty = item
        if certainty != 'derived' or not sources:
            return False, 0.0, ()
        field = fields.get(name)
        output_weight += _record_field_weight(
            getattr(field, 'type_name', None) or getattr(getattr(field, 'type', None), 'name', None)
        ) if field is not None else 1.0
        source_weight = 0.0
        for source in sources:
            # Root source type is not always available on the producer schema;
            # use the parent input schema when it is, otherwise a conservative
            # scalar planning weight.
            source_field = next((f for f in (getattr(getattr(parent_node, 'input_schema', None), 'fields', ()) or ())
                                 if str(getattr(f, 'name', '')) == source), None)
            source_weight += _record_field_weight(
                getattr(source_field, 'type_name', None) or getattr(getattr(source_field, 'type', None), 'name', None)
            ) if source_field is not None else 1.0
        total_source_weight += source_weight
        expression_complexity += 1.0 + 0.20 * len(sources)
        evidence.append((name, tuple(sources), round(source_weight, 3)))
    # Preserve only the dependency fields, then pay a bounded recomputation
    # term. A source set that is materially narrower than the derived output is
    # therefore able to beat projected materialization.
    source_fraction = total_source_weight / max(output_weight, 1.0)
    cost = 0.34 + 0.22 * min(2.5, source_fraction) + 0.07 * min(4.0, expression_complexity)
    return True, round(cost, 3), tuple(evidence)


def _record_recompute_provenance(parent_node, child_node, used_fields):
    """Return conservative evidence that selected fields can be recomputed.

    Provenance is attached to the producing ExecutionIR node. Recompute is
    considered supported only when every requested output field has a known
    dependency on source fields and the consumer is a pure deterministic map.
    Constants are safe to recreate too; unknown provenance is not.
    """
    provenance = dict((name, (sources, certainty)) for name, sources, certainty
                      in getattr(parent_node, 'record_field_provenance', ()) or ())
    if not used_fields:
        return False, 0.0, ()
    evidence=[]
    for name in used_fields:
        item = provenance.get(name)
        if item is None:
            return False, 0.0, ()
        sources, certainty = item
        if certainty == 'unknown':
            return False, 0.0, ()
        evidence.append((name, tuple(sources), certainty))
    # Derived/direct fields are equally valid semantic sources; the ratio is
    # only a bounded planning estimate used to price recomputation.
    complexity = sum(1.0 + 0.20 * len(sources) + (0.15 if certainty == 'derived' else 0.0)
                     for _, sources, certainty in evidence)
    return True, round(complexity, 3), tuple(evidence)


def _record_transitive_field_demand(ir, seeds, module=None):
    """Propagate Record field requirements backwards through Record maps.

    ``seeds`` contains fields required at downstream Record endpoints.  The
    returned contract is a graph-wide demand map: every Record-producing node
    receives the fields that must survive on its output so that all downstream
    requirements can eventually be satisfied.  The propagation is conservative
    when provenance is incomplete: a same-name field is retained when possible,
    otherwise the complete upstream Record schema is retained.
    """
    by_binding = ir.by_binding()
    by_result = {}
    for node in ir.nodes:
        result = getattr(node, 'result', None)
        if result is not None:
            by_result.setdefault(str(result), node)
    aliases = {}
    for node in ir.nodes:
        binding = getattr(node, 'binding', None)
        result = getattr(node, 'result', None)
        if binding is not None:
            aliases[str(binding)] = str(binding)
        if result is not None and binding is not None:
            aliases.setdefault(str(result), str(binding))
        elif result is not None:
            aliases.setdefault(str(result), str(result))

    children = {}
    for node in ir.nodes:
        for dep in getattr(node, 'dependencies', ()) or ():
            parent = by_binding.get(dep)
            if parent is not None:
                children.setdefault(parent.binding, []).append(node.binding)

    demands = {}
    for key, values in seeds.items():
        canonical = aliases.get(str(key), str(key))
        demands.setdefault(canonical, set()).update(str(v) for v in values)
    queue = list(sorted(demands))
    queued = set(queue)

    def resolve_parent(node):
        candidates = []
        for dep in getattr(node, 'dependencies', ()) or ():
            parent = by_binding.get(dep)
            if parent is None or parent.output_schema is None:
                continue
            if getattr(parent.output_schema, 'fields', None):
                candidates.append(parent)
        if not candidates:
            return None
        # Collection maps normally have exactly one concrete Record producer.
        # Keep the deterministic first candidate if auxiliary type dependencies
        # are present in the IR.
        return sorted(candidates, key=lambda n: str(n.binding))[0]

    while queue:
        binding = queue.pop(0)
        queued.discard(binding)
        node = by_binding.get(binding)
        if node is None or getattr(node, 'kind', None) != 'map':
            continue
        out_schema = getattr(node, 'output_schema', None)
        in_schema = getattr(node, 'input_schema', None)
        if out_schema is None or in_schema is None:
            continue
        out_fields = {str(getattr(f, 'name', '')) for f in getattr(out_schema, 'fields', ()) or ()}
        in_fields = {str(getattr(f, 'name', '')) for f in getattr(in_schema, 'fields', ()) or ()}
        needed = demands.get(binding, set()) & out_fields
        if not needed:
            continue
        parent = resolve_parent(node)
        if parent is None:
            continue
        parent_needed = demands.setdefault(parent.binding, set())
        before = len(parent_needed)
        provenance = dict(
            (str(name), (tuple(sources), certainty))
            for name, sources, certainty in (getattr(node, 'record_field_provenance', ()) or ())
        )
        # Some compatibility IR fixtures and a few optimized map forms do not
        # carry local provenance. When the AST is available, recover the exact
        # constructor dependencies here rather than falling back to every
        # same-name field. This also recognizes constant constructor fields,
        # which must not force an upstream field to survive.
        if module is not None and getattr(node, 'result', None) is not None:
            try:
                from .execution_ir import _node_expr, _record_field_provenance
                local = _record_field_provenance(
                    module, 'map', node.result, None, _node_expr(module, 'map', node.result), out_schema
                )
                if local:
                    provenance = dict((str(name), (tuple(sources), certainty)) for name, sources, certainty in local)
            except Exception:
                pass
        for field in sorted(needed):
            item = provenance.get(field)
            mapped = []
            if item is not None and item[1] == 'constant':
                mapped = []
            elif item is not None and item[1] != 'unknown':
                mapped = [str(source) for source in item[0] if str(source) in in_fields]
            if not mapped and item is None and field in in_fields:
                mapped = [field]
            if not mapped and item is not None and item[1] not in {'constant'} and field in in_fields:
                mapped = [field]
            if not mapped and item is None:
                # We cannot prove a narrower dependency. Keeping all input
                # fields is the safe global-plan fallback.
                mapped = sorted(in_fields)
            parent_needed.update(mapped)
        if len(parent_needed) != before and parent.binding not in queued:
            queue.append(parent.binding)
            queued.add(parent.binding)

    result_by_binding = {str(getattr(n, 'binding', '')): str(getattr(n, 'result', ''))
                         for n in ir.nodes if getattr(n, 'binding', None) is not None}
    return tuple(sorted((result_by_binding.get(binding, binding), tuple(sorted(fields)))
                        for binding, fields in demands.items() if fields))


def _record_plan_downstream_cost(record_plan, selected, choices_by_node, edges, ir, effective_cards, module=None):
    """Price each actual downstream consumer of selected Record endpoints.

    Record fusion is a graph-level decision, so its downstream term must use the
    real dependency edges rather than an AST-only consumer count. Each direct
    consumer is priced once, while the shared Record materialization/reuse
    overhead is charged once per endpoint. This makes fan-out a property of the
    actual execution graph and lets different consumer strategies affect the
    same global objective.
    """
    if record_plan is None:
        return 0.0, 0, (), 0.0, 1.0, 0.0, (), 0.0, (), 0.0, 0.0, (), (), 0.0, (), ()

    by_ir = ir.by_binding()
    by_result = {str(getattr(n, "result", "")): n for n in ir.nodes if getattr(n, "result", None) is not None}
    children = {}
    for edge in edges:
        children.setdefault(edge.before, []).append(edge.after)

    endpoints = set()
    segments = tuple(getattr(record_plan, "fused_segments", ()) or ())
    # Price not only segment terminals but also internal Record nodes that have
    # an external consumer. In a full fused segment, for example, r2 may feed
    # both the next Record map and a sort branch. r2 is therefore a real graph
    # materialization/reuse point even though it is not a segment endpoint.
    for segment in segments:
        if not segment:
            continue
        endpoints.add(segment[-1])
        for index, name in enumerate(segment[:-1]):
            resolved = name if name in children else next(
                (binding for binding in children if binding == name or binding.startswith(name + "#")),
                None,
            )
            if resolved is None:
                continue
            expected_next = segment[index + 1]
            if any(child != expected_next and not child.startswith(expected_next + "#") for child in children.get(resolved, ())):
                endpoints.add(name)

    # A selected Record plan may use aliases in future backends; only graph
    # bindings that exist in the IR can contribute downstream cost.
    details = []
    total = 0.0
    fanout_total = 0
    schema_width_total = 0.0
    schema_complexity_total = 0.0
    materialization_total = 0.0
    projected_fields = []
    projection_savings_total = 0.0
    materialization_strategies = []
    recompute_cost_total = 0.0
    partial_recompute_cost_total = 0.0
    recompute_provenance = []
    field_strategies = []
    for endpoint in sorted(endpoints):
        # ExecutionIR bindings may carry occurrence suffixes (for example
        # ``r3#1``) while Record-plan names come from the semantic AST
        # (``r3``). Resolve the AST name to its actual IR binding before
        # traversing dependency edges.
        resolved_endpoint = endpoint if endpoint in children else next(
            (name for name in children if name == endpoint or name.startswith(endpoint + "#")),
            None,
        )
        consumers = tuple(sorted(children.get(resolved_endpoint, ()))) if resolved_endpoint else ()
        if not consumers:
            continue
        fanout = len(consumers)
        fanout_total += fanout
        card = min(100.0, max(1.0, effective_cards.get(resolved_endpoint, 10.0)))
        schema_width, schema_complexity, field_count = _record_schema_profile(by_ir.get(resolved_endpoint))
        schema_width_total += schema_width
        schema_complexity_total += schema_complexity

        # Shared materialization is paid once. Reuse adds a bounded coordination
        # term for additional consumers instead of pretending every consumer
        # creates an independent materialization.
        # Materialization cost combines collection cardinality with the
        # structural size of the Record. The bounded terms keep this a
        # planning signal rather than a fake byte-level benchmark.
        width_factor = 1.0 + min(4.0, schema_width / 8.0)
        structure_factor = 1.0 + min(2.5, max(0.0, schema_complexity - 1.0))
        materialization_cost = (0.45 + 0.004 * card) * width_factor * structure_factor
        materialization_cost *= 1.0 + 0.08 * max(0, fanout - 1)
        materialization_total += materialization_cost
        total += materialization_cost

        for child in consumers:
            child_choice = choices_by_node.get(child)
            child_strategy = selected.get(child)
            if child_choice is None or child_strategy is None:
                continue
            child_score = _score(child_choice, child_strategy)
            parent_node = by_ir.get(resolved_endpoint)
            child_node = by_ir.get(child)
            transition = 0.0
            consumer_kind = getattr(child_node, "kind", "unknown") if child_node is not None else "unknown"
            consumer_weight = {
                "map": 0.70, "filter": 0.80, "conditional-pipeline": 1.00,
                "sort": 1.45, "aggregate": 1.65, "reduce": 1.65,
            }.get(consumer_kind, 1.0)
            if parent_node is not None and child_node is not None:
                transition = 0.20 * _transition_cost(
                    selected.get(resolved_endpoint, "generic"), child_strategy,
                    parent_node.kind, child_node.kind,
                )
            size_factor = 1.0 + min(3.0, card / 250.0)
            # Wider/structurally complex Records cost more to hand off to a
            # downstream consumer because more state must remain accessible.
            size_factor *= 1.0 + min(2.0, schema_width / 12.0)
            size_factor *= 1.0 + min(1.5, max(0.0, schema_complexity - 1.0))
            used_fields, full_record, projection_savings = _record_consumer_projection(parent_node, child_node)
            if used_fields:
                projected_fields.append((endpoint, f"{child}:{consumer_kind}", tuple(used_fields)))
            projection_savings_total += projection_savings
            # Compare three semantically distinct hand-off forms. ``full`` keeps
            # the complete Record, ``projected`` materializes only fields used by
            # this consumer, and ``recompute`` avoids carrying unused fields when
            # the consumer is pure/deterministic and the projected field set is
            # small enough that recomputation is cheaper than copying. The latter
            # is a planning candidate only; lowering remains responsible for
            # proving the concrete recomputation form legal.
            projection_fraction = 1.0 - projection_savings
            full_cost = 1.0 * size_factor
            projected_cost = max(0.35, projection_fraction) * size_factor
            # Recompute is legal only for a pure/deterministic Record-producing
            # consumer where the downstream map can derive its output fields
            # from the upstream Record. Filters/sorts/aggregates consume values
            # but do not provide a semantics-preserving place to recompute the
            # missing upstream fields, so they remain projection/full hand-offs.
            provenance_ok, provenance_cost, provenance_detail = _record_recompute_provenance(
                parent_node, child_node, used_fields
            )
            can_recompute = (consumer_kind == "map" and
                             bool(getattr(child_node, "pure", False)) and
                             bool(getattr(child_node, "deterministic", True)) and
                             not full_record and provenance_ok)
            recompute_cost = (0.42 + 0.18 * projection_fraction +
                              0.08 * max(0, len(used_fields) - 1) +
                              0.06 * provenance_cost)
            partial_ok, partial_cost, partial_detail = _record_partial_recompute_candidate(
                parent_node, child_node, used_fields
            )
            # Choose a hand-off strategy independently for each requested field.
            # This is an additional refinement of the consumer-level decision: the
            # legacy aggregate mode remains available for compatibility, while
            # `record_field_strategies` exposes the finer-grained choices.
            field_candidates = []
            field_names = tuple(used_fields) if used_fields else tuple()
            provenance_map = dict((name, (sources, certainty))
                                  for name, sources, certainty in (getattr(parent_node, 'record_field_provenance', ()) or ()))
            for field_name in field_names:
                field_obj = next((f for f in (getattr(getattr(parent_node, 'output_schema', None), 'fields', ()) or ())
                                  if str(getattr(f, 'name', '')) == field_name), None)
                fw = _record_field_weight(
                    getattr(field_obj, 'type_name', None) or getattr(getattr(field_obj, 'type', None), 'name', None)
                ) if field_obj is not None else 1.0
                fcandidates = [(0.52 * fw, 'full', ())]
                if not full_record:
                    fcandidates.append((max(0.18, 0.55 * fw), 'projected', ()))
                item = provenance_map.get(field_name)
                if can_recompute and item is not None and item[1] != 'unknown':
                    sources, certainty = item
                    expr_cost = 0.42 + 0.18 * max(0, len(sources) - 1) + (0.06 if certainty == 'derived' else 0.0)
                    fcandidates.append((expr_cost * max(0.5, min(2.0, fw)), 'recompute', tuple(sources)))
                if partial_ok and item is not None and item[1] == 'derived':
                    sources = tuple(item[0])
                    source_cost = 0.30 + 0.14 * len(sources)
                    fcandidates.append((source_cost * max(0.5, min(1.8, fw)), 'partial-recompute', sources))
                fcost, fmode, fdetail = min(fcandidates, key=lambda item: (item[0], item[1]))
                field_strategies.append((endpoint, f"{child}:{consumer_kind}", field_name, fmode, round(fcost, 3), tuple(fdetail)))
                field_candidates.append((fcost, fmode, fdetail, field_name))

            # Keep the established consumer-level strategy selection as the
            # aggregate contract, while field-level choices are recorded above.
            candidates = [(full_cost, "full", ())]
            if not full_record:
                candidates.append((projected_cost, "projected", ()))
            if can_recompute:
                candidates.append((recompute_cost, "recompute", provenance_detail))
            if partial_ok:
                candidates.append((partial_cost, "partial-recompute", partial_detail))
            chosen_handoff, handoff_mode, chosen_detail = min(
                candidates, key=lambda item: (item[0], item[1])
            )
            if handoff_mode == "recompute":
                recompute_cost_total += chosen_handoff * consumer_weight
                recompute_provenance.append((endpoint, f"{child}:{consumer_kind}", chosen_detail))
            elif handoff_mode == "partial-recompute":
                partial_recompute_cost_total += chosen_handoff * consumer_weight
                recompute_provenance.append((endpoint, f"{child}:{consumer_kind}:partial", chosen_detail))
            materialization_strategies.append((endpoint, handoff_mode, round(chosen_handoff, 3), tuple(used_fields)))
            # A consumer that touches only part of a Record can receive a
            # projected hand-off. Reduce its hand-off cost by the estimated
            # unused field weight, while keeping a conservative floor.
            if handoff_mode == "projected":
                size_factor *= max(0.35, chosen_handoff)
            elif handoff_mode == "recompute":
                size_factor *= min(0.95, chosen_handoff)
            elif not full_record and projection_savings > 0.0:
                size_factor *= max(0.35, 1.0 - 0.65 * projection_savings)
            weighted = (0.10 * child_score + transition) * consumer_weight
            weighted *= size_factor
            if consumer_kind in {"sort", "aggregate", "reduce"}:
                weighted += 0.18 * consumer_weight * min(3.0, card / 100.0)
            total += weighted
            details.append((endpoint, f"{child}:{consumer_kind}", round(weighted, 3)))

    # Build the shared retention seeds from all downstream consumers, then
    # propagate those requirements backwards through the Record map graph.
    # This turns the fan-out contract into a transitive field-demand graph
    # instead of a single-boundary union.
    grouped_requirements = {}
    for endpoint, consumer, field_name, strategy, _cost, source_fields in field_strategies:
        required = grouped_requirements.setdefault(endpoint, set())
        if strategy in {"recompute", "partial-recompute"}:
            required.update(str(source) for source in (source_fields or ()))
        else:
            required.add(str(field_name))
    fanout_requirements = _record_transitive_field_demand(ir, grouped_requirements, module=module)

    # When several downstream branches require the same derived field, compare
    # carrying/recomputing it independently with computing it once at the
    # shared Record point and reusing the resulting field. The comparison is
    # deliberately based on the already selected per-consumer field costs, so
    # this remains part of the same global objective rather than a second
    # optimizer. Only pure map consumers participate in the shared candidate.
    shared_groups = {}
    for endpoint, consumer, field_name, strategy, cost, source_fields in field_strategies:
        if not str(consumer).endswith(':map'):
            continue
        parent = by_ir.get(str(endpoint)) or by_result.get(str(endpoint))
        provenance = dict((str(name), (tuple(sources), certainty))
                          for name, sources, certainty in
                          (getattr(parent, 'record_field_provenance', ()) or ())) if parent is not None else {}
        if module is not None and parent is not None and getattr(parent, 'result', None) is not None:
            try:
                from .execution_ir import _node_expr, _record_field_provenance
                local = _record_field_provenance(
                    module, 'map', parent.result, None, _node_expr(module, 'map', parent.result),
                    getattr(parent, 'output_schema', None)
                )
                if local:
                    provenance = dict((str(name), (tuple(sources), certainty)) for name, sources, certainty in local)
            except Exception:
                pass
        item = provenance.get(str(field_name))
        if item is None or item[1] != 'derived':
            continue
        sources = tuple(source_fields) or tuple(item[0])
        if not sources:
            continue
        shared_groups.setdefault((endpoint, field_name), []).append(
            (consumer, float(cost), sources, strategy)
        )
    shared_savings = 0.0
    shared_decisions = []
    for (endpoint, field_name), rows in sorted(shared_groups.items()):
        consumers = tuple(sorted({row[0] for row in rows}))
        if len(consumers) < 2:
            continue
        source_union = tuple(sorted({src for _, _, sources, _ in rows for src in sources}))
        individual = sum(row[1] for row in rows)
        # A shared expression is evaluated once; each additional branch pays a
        # small deterministic reuse/hand-off cost. Direct fields have no useful
        # recomputation expression, so they are excluded by the provenance
        # check above in the usual case.
        shared = min(row[1] for row in rows) + 0.10 * (len(consumers) - 1)
        savings = max(0.0, individual - shared)
        if savings <= 0.0:
            continue
        shared_savings += savings
        shared_decisions.append((endpoint, field_name, source_union, round(individual, 3), round(shared, 3)))
    total = max(0.0, total - shared_savings)

    return (round(total, 3), fanout_total, tuple(details),
            round(schema_width_total, 3), round(schema_complexity_total, 3),
            round(materialization_total, 3), tuple(projected_fields),
            round(projection_savings_total, 3), tuple(materialization_strategies),
            round(recompute_cost_total, 3), round(partial_recompute_cost_total, 3), tuple(recompute_provenance),
            tuple(fanout_requirements), round(shared_savings, 3), tuple(shared_decisions), tuple(field_strategies))

def _evaluate(selected, choices_by_node, edges, fusion_groups, ir, record_plan=None, module=None):
    local = sum(_score(choices_by_node[n], selected[n]) for n in selected)
    by_ir = ir.by_binding()
    effective_cards = _effective_cardinalities(ir)
    (record_downstream_cost, record_downstream_fanout, record_downstream_consumers,
     record_schema_width, record_schema_complexity, record_materialization_cost,
     record_projected_fields, record_projection_savings, record_materialization_strategies,
     record_recompute_cost, record_partial_recompute_cost, record_recompute_provenance, record_fanout_field_requirements, record_shared_recompute_savings, record_shared_recompute_decisions, record_field_strategies) = _record_plan_downstream_cost(
        record_plan, selected, choices_by_node, edges, ir, effective_cards, module=module
    )
    profile_transition_cost, parallel_islands, materialization_reuse_cost, peak_live_cardinality, profile_signature = _profile_global_cost(selected, edges, ir, effective_cards)
    execution_regions = _execution_region_modes(selected, edges, ir)
    execution_region_cost = round(sum(0.06 * size + 0.12 * mixed for _, size, mixed in execution_regions), 3)
    selectivities = tuple(sorted((n.binding, round(_selectivity(n), 3)) for n in ir.nodes))
    downstream = _downstream_pressure(edges, effective_cards)
    fused_edges = set()
    for group in fusion_groups:
        terminal = group.terminal
        if selected.get(terminal, "") == group.strategy:
            chain = group.nodes
            fused_edges.update(zip(chain, chain[1:]))
    boundaries = 0
    chain_cost = 0.0
    cardinality_weighted_cost = 0.0
    selectivity_weighted_cost = 0.0
    strategy_context_cost = 0.0
    transitions = 0
    estimated_peak_cardinality = None
    for node in ir.nodes:
        if node.cardinality is not None:
            estimated_peak_cardinality = max(estimated_peak_cardinality or 0, int(node.cardinality))
        elif node.data_shape is not None and node.data_shape.upper is not None:
            estimated_peak_cardinality = max(estimated_peak_cardinality or 0, int(node.data_shape.upper))
    for edge in edges:
        pair = (edge.before, edge.after)
        if pair in fused_edges:
            continue
        parent = selected.get(edge.before)
        child = selected.get(edge.after)
        if parent is None or child is None:
            continue
        if materialization_profile(parent) != "streaming-when-fused":
            boundaries += 1
        pn = by_ir.get(edge.before)
        cn = by_ir.get(edge.after)
        if pn is not None and cn is not None:
            transition = _transition_cost(parent, child, pn.kind, cn.kind)
            chain_cost += transition
            card = effective_cards.get(edge.before, 10.0)
            # Large intermediate collections make a boundary more expensive
            # than the same semantic transition over a scalar. The multiplier
            # is deliberately bounded and deterministic; it is not a hardware
            # benchmark.
            cardinality_factor = 1.0 + min(8.0, max(0.0, card) / 1000.0)
            cardinality_weighted_cost += transition * cardinality_factor
            # Selectivity discounts downstream transition cost when a prior
            # operation is statically expected to reduce the collection. This
            # affects only planning cost; it never changes program semantics.
            downstream_card = effective_cards.get(edge.after, card)
            selectivity_ratio = min(1.0, downstream_card / max(card, 1.0))
            selectivity_weighted_cost += transition * selectivity_ratio
            # A strategy at the head of a long dependency chain has more
            # global impact than an isolated node. Keep this bounded and
            # deterministic. The context term is intentionally small: it
            # refines choices rather than overriding semantic legality.
            pressure = downstream.get(edge.before, 0.0)
            if parent in {"graph-shortest-path", "bidirectional-dijkstra", "a-star-landmark"}:
                strategy_context_cost += 0.001 * min(100.0, pressure)
            if transition > 0:
                transitions += 1
    boundary_cost = boundaries * 1.5
    record_fusion_cost = 0.0
    record_fusion_fusions = record_fusion_partial = record_fusion_materialized = 0
    if record_plan is not None:
        record_fusion_fusions = int(getattr(record_plan, "record_transform_fusions", 0))
        record_fusion_partial = int(getattr(record_plan, "record_transform_partial", 0))
        record_fusion_materialized = int(getattr(record_plan, "record_transform_materialized", 0))
        # Account for the Record planner's selected transformation profile in
        # the same whole-graph objective. This is a bounded relative planning
        # term: fusion still avoids materialization, while partial/materialized
        # decisions retain a larger coordination cost.
        structural_record_cost = (0.25 * record_fusion_fusions +
                                   1.50 * record_fusion_partial +
                                   2.00 * record_fusion_materialized)
        # The Record planner's intrinsic estimate remains a small structural
        # term. Actual downstream consumer cost is computed from the global IR
        # graph above, so fan-out and consumer strategy choices participate in
        # the same objective.
        record_fusion_cost = structural_record_cost + record_downstream_cost
    total = (local + boundary_cost + chain_cost + cardinality_weighted_cost +
             record_fusion_cost +
             selectivity_weighted_cost + strategy_context_cost +
             profile_transition_cost + materialization_reuse_cost +
             0.05 * parallel_islands + 0.001 * min(1000, peak_live_cardinality or 0) + execution_region_cost)
    return GlobalPlanCost(
        local_cost=round(local, 3),
        boundary_cost=round(boundary_cost, 3),
        chain_cost=round(chain_cost, 3),
        total_cost=round(total, 3),
        materialization_boundaries=boundaries,
        fused_internal_edges=len(fused_edges),
        strategy_transitions=transitions,
        cardinality_weighted_cost=round(cardinality_weighted_cost, 3),
        estimated_peak_cardinality=estimated_peak_cardinality,
        selectivity_weighted_cost=round(selectivity_weighted_cost, 3),
        estimated_selectivities=selectivities,
        downstream_pressure=tuple(sorted((k, round(v, 3)) for k, v in downstream.items())),
        strategy_context_cost=round(strategy_context_cost, 3),
        profile_transition_cost=profile_transition_cost,
        parallel_islands=parallel_islands,
        materialization_reuse_cost=materialization_reuse_cost,
        peak_live_cardinality=peak_live_cardinality,
        profile_signature=profile_signature,
        execution_region_cost=execution_region_cost,
        execution_regions=execution_regions,
        record_fusion_cost=round(record_fusion_cost, 3),
        record_fusion_fusions=record_fusion_fusions,
        record_fusion_partial=record_fusion_partial,
        record_fusion_materialized=record_fusion_materialized,
        record_downstream_cost=record_downstream_cost,
        record_downstream_fanout=record_downstream_fanout,
        record_downstream_consumers=record_downstream_consumers,
        record_schema_width=record_schema_width,
        record_schema_complexity=record_schema_complexity,
        record_materialization_cost=record_materialization_cost,
        record_projected_fields=record_projected_fields,
        record_projection_savings=record_projection_savings,
        record_materialization_strategies=record_materialization_strategies,
        record_recompute_cost=record_recompute_cost,
        record_partial_recompute_cost=record_partial_recompute_cost,
        record_recompute_provenance=record_recompute_provenance,
        record_field_strategies=record_field_strategies,
        record_fanout_field_requirements=record_fanout_field_requirements,
        record_shared_recompute_savings=record_shared_recompute_savings,
        record_shared_recompute_decisions=record_shared_recompute_decisions,
        record_plan_mode=getattr(record_plan, "mode", "none") if record_plan is not None else "none",
        record_plan_alternatives=int(getattr(record_plan, "alternatives", 1)) if record_plan is not None else 1,
    )


def optimize_strategy_choices(edges, fusion_groups, choices: tuple[StrategyChoice, ...], ir, record_plan=None, record_plan_options=None, module=None):
    """Select a minimum-cost legal strategy combination for the whole graph.

    Unlike the earlier coordinate-descent optimizer, this routine searches the
    combination space itself. Small spaces are exhaustively enumerated. Larger
    spaces use deterministic branch-and-bound with a conservative lower bound
    consisting only of the minimum remaining local strategy costs. Since all
    cross-node penalties are non-negative, that bound is safe.

    Candidate legality is never expanded here: only alternatives already
    produced by the local strategy planner are considered.
    """
    by_choice = {c.node: c for c in choices}
    nodes = tuple(c.node for c in choices)
    # Record alternatives are part of the same global objective. They are
    # evaluated at every complete strategy assignment, so strategy and Record
    # decisions compete rather than being chosen in isolated passes.
    record_options = tuple(record_plan_options or (record_plan,))
    record_options = tuple(o for o in record_options if o is not None) or (None,)
    candidate_map = {}
    for choice in choices:
        candidates = tuple(dict.fromkeys(choice.alternatives or (choice.strategy,)))
        if choice.strategy not in candidates:
            candidates = (choice.strategy,) + candidates
        candidate_map[choice.node] = tuple(sorted(candidates, key=lambda x: (x,)))

    import math
    search_space = math.prod(len(candidate_map[n]) for n in nodes) if nodes else 1
    search_space *= len(record_options)
    # Keep exhaustive enumeration practical while retaining an exact
    # deterministic search for larger spaces whenever the lower bound prunes.
    evaluation_budget = 100_000
    selected = {}
    best_selected = None
    best_cost = None
    best_key = None
    best_record_plan = record_options[0] if record_options else None
    evaluated = 0
    exhausted = True

    min_suffix = [0.0] * (len(nodes) + 1)
    for i in range(len(nodes) - 1, -1, -1):
        choice = by_choice[nodes[i]]
        min_suffix[i] = min_suffix[i + 1] + min(_score(choice, c) for c in candidate_map[nodes[i]])

    def visit(index, local_sum):
        nonlocal best_selected, best_cost, best_key, evaluated, exhausted
        if evaluated >= evaluation_budget:
            exhausted = False
            return
        # All non-local components of the objective are non-negative, so this
        # is a valid lower bound for every completion of the partial plan.
        if best_cost is not None and local_sum + min_suffix[index] > best_cost:
            return
        if index == len(nodes):
            evaluated += 1
            for option_index, option in enumerate(record_options):
                cost = _evaluate(selected, by_choice, edges, fusion_groups, ir, option, module)
                key = (tuple(selected[n] for n in nodes), option_index)
                if best_cost is None or (cost.total_cost, key) < (best_cost, best_key):
                    best_cost = cost.total_cost
                    best_key = key
                    best_selected = dict(selected)
                    best_record_plan = option
            return

        node = nodes[index]
        choice = by_choice[node]
        for candidate in candidate_map[node]:
            selected[node] = candidate
            visit(index + 1, local_sum + _score(choice, candidate))
            if not exhausted:
                return
        selected.pop(node, None)

    visit(0, 0.0)

    # Empty choice sets are legal only for an empty graph.
    if best_selected is None:
        best_selected = {}
        best_cost = 0.0

    final_cost = _evaluate(best_selected, by_choice, edges, fusion_groups, ir, best_record_plan, module)
    # Field-level Record strategies are part of the selected Record decision,
    # not merely diagnostic output. Attach the authoritative result to the
    # chosen immutable RecordFusionDecision so selected plans and backends
    # consume exactly the same field strategy contract.
    if best_record_plan is not None:
        field_strategies = tuple(final_cost.record_field_strategies)
        fanout_requirements = tuple(final_cost.record_fanout_field_requirements)
        record_shared_recompute_decisions = tuple(final_cost.record_shared_recompute_decisions)
        # The combined Record plan is the authoritative planning envelope.
        # Store the field contract on that envelope; individual immutable
        # decisions remain unchanged so they can continue to be shared by the
        # option enumerator without mutation.
        try:
            best_record_plan.field_strategies = field_strategies
            best_record_plan.record_fanout_field_requirements = fanout_requirements
            best_record_plan.record_shared_recompute_decisions = tuple(record_shared_recompute_decisions)
        except AttributeError:
            best_record_plan = replace(
                best_record_plan,
                field_strategies=field_strategies,
                record_fanout_field_requirements=fanout_requirements,
                record_shared_recompute_decisions=tuple(record_shared_recompute_decisions),
            )
        final_cost = replace(final_cost, record_plan=best_record_plan)
    if search_space <= evaluation_budget and exhausted:
        mode = "exhaustive"
        optimality = "exhaustive"
    else:
        mode = "bounded-branch-and-bound"
        optimality = "bounded-search" if not exhausted else "branch-and-bound-exact"

    final_cost = replace(
        final_cost,
        search_mode=mode,
        strategy_combinations_evaluated=evaluated,
        strategy_search_space=search_space,
        global_optimality=optimality,
        record_plan=best_record_plan,
    )

    updated = []
    for choice in choices:
        strategy = best_selected[choice.node]
        if strategy == choice.strategy:
            updated.append(choice)
            continue
        updated.append(StrategyChoice(
            node=choice.node,
            strategy=strategy,
            reason=choice.reason + "; global whole-graph strategy optimization selected this legal alternative",
            executable=choice.executable,
            alternatives=choice.alternatives,
            scores=choice.scores,
            profile=choice.profile,
            rejections=choice.rejections,
            runtime_supported=choice.runtime_supported,
        ))
    return tuple(updated), final_cost

