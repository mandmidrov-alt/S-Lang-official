from __future__ import annotations
from dataclasses import dataclass
from .ast import Binary, Compare, Logical, Call, Field, Literal, Name, Property, Expr, FilterOp, MapOp, Predicate, source_span_of
from .record_fusion import find_record_chains, plan_record_chain, analyze_record_downstream, enumerate_record_chain_plans

@dataclass(frozen=True)
class OptimizationReport:
    constant_folds: int = 0
    filter_fusions: int = 0
    map_fusions: int = 0
    pipeline_fusions: int = 0
    record_transform_fusions: int = 0
    identity_maps_removed: int = 0
    record_transform_partial: int = 0
    record_transform_materialized: int = 0
    record_downstream_pressure: float = 0.0
    record_downstream_fanout: int = 0

    @property
    def total(self) -> int:
        return self.constant_folds + self.filter_fusions + self.map_fusions + self.pipeline_fusions + self.record_transform_fusions + self.identity_maps_removed


def _literal_value(expr):
    return expr.value if isinstance(expr, Literal) else None


def _fold(expr: Expr):
    """Fold only closed scalar arithmetic/comparisons. No user functions."""
    if isinstance(expr, Binary):
        left, lc = _fold(expr.left)
        right, rc = _fold(expr.right)
        if isinstance(left, Literal) and isinstance(right, Literal):
            a, b = left.value, right.value
            try:
                if expr.op == '+': return Literal(a + b), True
                if expr.op == '-': return Literal(a - b), True
                if expr.op == '*': return Literal(a * b), True
                if expr.op == '/': return Literal(a / b), True
                if expr.op == '%':
                    import math
                    if b == 0: raise ZeroDivisionError('modulo by zero')
                    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                        raise TypeError('operator % requires numeric operands')
                    return Literal(math.fmod(a, b)), True
                if expr.op == '^': return Literal(a ** b), True
            except (ArithmeticError, TypeError, ValueError):
                pass
        return Binary(expr.op, left, right), lc or rc
    if isinstance(expr, Compare):
        left, lc = _fold(expr.left)
        right, rc = _fold(expr.right)
        if isinstance(left, Literal) and isinstance(right, Literal):
            a, b = left.value, right.value
            try:
                result = {'>=': a >= b, '<=': a <= b, '==': a == b,
                          '!=': a != b, '>': a > b, '<': a < b}[expr.op]
                return Literal(result), True
            except (TypeError, ValueError):
                pass
        return Compare(expr.op, left, right), lc or rc
    if isinstance(expr, Logical):
        left, lc = _fold(expr.left)
        if expr.op == 'not':
            if isinstance(left, Literal) and isinstance(left.value, bool): return Literal(not left.value), True
            return Logical('not', left), lc
        right, rc = _fold(expr.right)
        if isinstance(left, Literal) and isinstance(right, Literal) and isinstance(left.value, bool) and isinstance(right.value, bool):
            return Literal((left.value and right.value) if expr.op == 'and' else (left.value or right.value)), True
        return Logical(expr.op, left, right), lc or rc
    if isinstance(expr, Field):
        base, c = _fold(expr.base)
        return Field(base, expr.name), c
    if isinstance(expr, Property):
        base, c = _fold(expr.base)
        return Property(base, expr.name), c
    if isinstance(expr, Call):
        args = []
        changed = False
        for arg in expr.args:
            new, c = _fold(arg)
            args.append(new); changed |= c
        return Call(expr.name, tuple(args)), changed
    return expr, False


def _substitute_item(expr: Expr, replacement: Expr) -> Expr:
    """Replace the current collection element with an expression.

    Both `item` and the internal row base are accepted because the parser uses
    both representations for scalar and row-shaped collection expressions.
    """
    if isinstance(expr, Name):
        if expr.name in ('item', 'row'):
            return replacement
        return expr
    if isinstance(expr, Field):
        return Field(_substitute_item(expr.base, replacement), expr.name)
    if isinstance(expr, Property):
        return Property(_substitute_item(expr.base, replacement), expr.name)
    if isinstance(expr, Binary):
        return Binary(expr.op, _substitute_item(expr.left, replacement), _substitute_item(expr.right, replacement))
    if isinstance(expr, Compare):
        return Compare(expr.op, _substitute_item(expr.left, replacement), _substitute_item(expr.right, replacement))
    if isinstance(expr, Logical):
        return Logical(expr.op, _substitute_item(expr.left, replacement), _substitute_item(expr.right, replacement) if expr.right is not None else None)
    if isinstance(expr, Call):
        return Call(expr.name, tuple(_substitute_item(a, replacement) for a in expr.args))
    return expr


def _is_identity(expr: Expr) -> bool:
    return isinstance(expr, Name) and expr.name in ('item', 'row')


def _record_constructor(expr, schemas):
    """Return (schema, args) for a typed Record constructor, if available."""
    if not isinstance(expr, Call):
        return None
    schema = schemas.get(expr.name)
    if schema is None:
        return None
    fields = tuple(getattr(schema, "fields", ()))
    if len(expr.args) != len(fields):
        return None
    return schema, tuple(expr.args)


def _record_field_substitute(expr: Expr, source_schema, replacements):
    """Inline row.field references from an intermediate Record schema.

    Only pure structural expressions are accepted. User function calls and
    arbitrary row expressions are deliberately excluded because duplicating
    them could alter observable effects or evaluation cost.
    """
    if isinstance(expr, Literal):
        return expr, True
    if isinstance(expr, Name):
        # A bare row/item is not a scalar field expression in this transform.
        return (expr, expr.name not in ("row", "item"))
    if isinstance(expr, (Field, Property)):
        if isinstance(expr.base, Name) and expr.base.name in ("row", "item"):
            replacement = replacements.get(expr.name)
            return (replacement, replacement is not None)
        return expr, False
    if isinstance(expr, Binary):
        left, ok_l = _record_field_substitute(expr.left, source_schema, replacements)
        right, ok_r = _record_field_substitute(expr.right, source_schema, replacements)
        return Binary(expr.op, left, right), ok_l and ok_r
    if isinstance(expr, Compare):
        left, ok_l = _record_field_substitute(expr.left, source_schema, replacements)
        right, ok_r = _record_field_substitute(expr.right, source_schema, replacements)
        return Compare(expr.op, left, right), ok_l and ok_r
    if isinstance(expr, Logical):
        left, ok_l = _record_field_substitute(expr.left, source_schema, replacements)
        if expr.right is None:
            return Logical(expr.op, left), ok_l
        right, ok_r = _record_field_substitute(expr.right, source_schema, replacements)
        return Logical(expr.op, left, right), ok_l and ok_r
    # Conditional is imported lazily here to keep the existing import surface.
    from .ast import Conditional
    if isinstance(expr, Conditional):
        cond, ok_c = _record_field_substitute(expr.condition, source_schema, replacements)
        then_expr, ok_t = _record_field_substitute(expr.then_expr, source_schema, replacements)
        else_expr, ok_e = _record_field_substitute(expr.else_expr, source_schema, replacements)
        return Conditional(cond, then_expr, else_expr), ok_c and ok_t and ok_e
    # Calls may contain user functions/effects. Do not duplicate them during
    # this optimization; the ordinary Record transform remains available.
    return expr, False


def _record_map_consumers(program, result):
    """Find executable operations that consume a map result."""
    ast = program.ast
    consumers = []
    for collection in (
        ast.maps, ast.filters, ast.sorts, ast.aggregates, ast.reduces,
        ast.conditional_pipelines,
    ):
        for op in collection:
            if getattr(op, "source", None) == result:
                consumers.append(op)
    return consumers


def _fuse_record_transform_pair(first, second, schemas):
    """Compose two schema-changing Record constructors when structurally safe."""
    first_info = _record_constructor(first.expr, schemas)
    second_info = _record_constructor(second.expr, schemas)
    if first_info is None or second_info is None:
        return None
    intermediate_schema, first_args = first_info
    final_schema, second_args = second_info
    intermediate_fields = tuple(getattr(intermediate_schema, "fields", ()))
    if len(intermediate_fields) != len(first_args) or len(second_args) != len(getattr(final_schema, "fields", ())):
        return None

    # Map intermediate field names to the exact expressions that produce them.
    replacements = {field.name: arg for field, arg in zip(intermediate_fields, first_args)}
    composed = []
    for arg in second_args:
        value, supported = _record_field_substitute(arg, intermediate_schema, replacements)
        if not supported:
            return None
        composed.append(value)
    return MapOp(first.source, Call(second.expr.name, tuple(composed)), second.result)


def enumerate_record_plan_options(program, max_options: int = 256):
    """Build deterministic combined Record-plan alternatives for global search."""
    import itertools
    schemas = getattr(program.ast, "_record_schemas", {}) or {}
    chains = find_record_chains(list(program.ast.maps), schemas)
    if not chains:
        return ()
    per_chain = []
    for chain in chains:
        options = enumerate_record_chain_plans(chain, schemas, analyze_record_downstream(program, chain))
        if options:
            per_chain.append(options)
    if not per_chain:
        return ()
    combined = []
    for combo in itertools.product(*per_chain):
        fused = sum((d.fused_segments for d in combo), ())
        boundaries = sum((d.materialization_boundaries for d in combo), ())
        modes = tuple(d.mode for d in combo)
        from types import SimpleNamespace
        combined.append(SimpleNamespace(
            decisions=combo,
            fused_segments=fused,
            materialization_boundaries=boundaries,
            mode="full" if all(m == "full" for m in modes) else ("materialized" if all(m == "materialized" for m in modes) else "partial"),
            estimated_cost=round(sum(d.estimated_cost for d in combo), 3),
            record_transform_fusions=sum(max(0, len(seg) - 1) for d in combo for seg in d.fused_segments),
            record_transform_partial=sum(m == "partial" for m in modes),
            record_transform_materialized=sum(m == "materialized" for m in modes),
            downstream_pressure=round(sum(d.downstream_pressure for d in combo), 3),
            downstream_fanout=sum(d.downstream_fanout for d in combo),
            field_strategies=(),
            alternatives=1,
        ))
    combined.sort(key=lambda x: (x.estimated_cost, tuple(d.fused_segments for d in x.decisions)))
    total = len(combined)
    for item in combined[:max_options]:
        item.alternatives = total
    return tuple(combined[:max_options])


def optimize_program(program) -> OptimizationReport:
    """Apply semantics-preserving optimizations to the declarative dataflow.

    The optimizer deliberately works on semantic operations rather than source
    syntax. It may therefore change the implementation strategy without
    changing S-Lang's observable meaning.
    """
    folds = 0
    # Closed-expression folding is applied when expressions are rebuilt during
    # collection-map fusion. Top-level/function AST nodes include frozen
    # declarations in the current implementation, so they are intentionally left intact.

    # Filter fusion is semantic conjunction: consecutive filters can be
    # collapsed when the intermediate collection is not observable. This
    # removes an intermediate pass without changing the selected elements.
    filters = list(program.ast.filters)
    filter_fusions = 0
    observed = set()
    for name, field in (program.shows or []): observed.add(name)
    for expr in (program.show_exprs or []):
        if isinstance(expr, Name): observed.add(expr.name)
    changed = True
    while changed:
        changed = False
        for i, second in enumerate(filters):
            first_index = next((j for j, first in enumerate(filters) if j != i and first.result == second.source), None)
            if first_index is None: continue
            first = filters[first_index]
            if first.result in observed: continue
            # A filter pair is fusible only when the second filter consumes
            # the materialized result of the first filter directly.  Logical
            # names may be rebound several times, so a map or sort between
            # the two filters changes the element type/order even when both
            # operations happen to use the same source/result identifier.
            # Combining their predicates would evaluate the later predicate
            # against the earlier collection (for example Record instead of
            # Number after `map`).
            first_span = source_span_of(first)
            second_span = source_span_of(second)
            if first_span is not None and second_span is not None:
                first_pos = (first_span.start.line, first_span.start.column)
                second_pos = (second_span.start.line, second_span.start.column)
                intervening = False
                for candidate in (list(program.ast.maps) + list(program.ast.sorts) +
                                 list(program.ast.aggregates) + list(program.ast.reduces) +
                                 list(getattr(program.ast, "conditional_pipelines", ()))):
                    if getattr(candidate, "source", None) != first.result:
                        continue
                    span = source_span_of(candidate)
                    if span is None:
                        continue
                    pos = (span.start.line, span.start.column)
                    if first_pos < pos < second_pos:
                        intervening = True
                        break
                if intervening:
                    continue
            combined = Logical('and', first.predicate.expr, second.predicate.expr)
            combined, folded = _fold(combined)
            filters[first_index] = FilterOp(first.source, Predicate(combined), second.result)
            del filters[i]
            filter_fusions += 1
            folds += int(folded)
            changed = True
            break
    program.ast.filters = filters

    # Record-transform fusion is schema-aware. Unlike generic scalar map
    # fusion, it substitutes intermediate row.field references using the
    # semantic Record schema, allowing two executable Record transformations
    # to become one without materializing the intermediate Record.
    maps = list(program.ast.maps)
    record_transform_fusions = 0
    record_transform_partial = 0
    record_transform_materialized = 0
    record_schemas = getattr(program.ast, "_record_schemas", {}) or {}
    # The Record planner chooses fusion boundaries for each maximal typed chain.
    # A pair may be fused only when it belongs to the same selected segment.
    planned_pairs = set()
    record_materialization_boundaries = set()
    for chain in find_record_chains(maps, record_schemas):
        decision = plan_record_chain(chain, record_schemas, analyze_record_downstream(program, chain))
        if decision is None:
            continue
        program._record_fusion_decisions = getattr(program, "_record_fusion_decisions", []) + [decision]
        if decision.mode == "partial":
            record_transform_partial += 1
        elif decision.mode == "materialized":
            record_transform_materialized += 1
        for boundary in decision.materialization_boundaries:
            record_materialization_boundaries.add(boundary)
        for segment_index, segment in enumerate(decision.fused_segments):
            pairs = list(zip(segment, segment[1:]))
            # A later segment starts at an explicit materialization boundary.
            # Keep that boundary operation intact; fuse only its suffix.
            if segment_index > 0 and pairs:
                pairs = pairs[1:]
            planned_pairs.update(pairs)

    changed = True
    while changed and record_schemas:
        changed = False
        for i, second in enumerate(maps):
            first_index = next((j for j, first in enumerate(maps)
                                if j != i and first.result == second.source), None)
            if first_index is None:
                continue
            first = maps[first_index]
            if (first.result, second.result) not in planned_pairs:
                continue
            if first.result in observed:
                continue
            if len(_record_map_consumers(program, first.result)) != 1:
                continue
            composed = _fuse_record_transform_pair(first, second, record_schemas)
            if composed is None:
                continue
            maps[first_index] = composed
            del maps[i]
            record_transform_fusions += 1
            changed = True
            break

    # Map fusion is general: map f followed by map g becomes map g(f(item)).
    map_fusions = 0
    fused_intermediates = {}
    observed = set()
    for name, field in (program.shows or []):
        observed.add(name)
    for expr in (program.show_exprs or []):
        if isinstance(expr, Name): observed.add(expr.name)
    changed = True
    while changed:
        changed = False
        for i, second in enumerate(maps):
            first_index = next((j for j, first in enumerate(maps)
                                if j != i and first.result == second.source), None)
            if first_index is None:
                continue
            first = maps[first_index]
            if first.result in record_materialization_boundaries:
                continue
            if first.result in observed or second.result in observed:
                continue
            # A map pair is fusible only when no collection stage consumes the
            # first result between the two source statements.  In-place
            # rebinding makes logical names identical across versions, so a
            # simple `first.result == second.source` test is insufficient:
            # `map -> filter -> map` must retain the filter boundary.
            first_span = source_span_of(first)
            second_span = source_span_of(second)
            if first_span is not None and second_span is not None:
                first_pos = (first_span.start.line, first_span.start.column)
                second_pos = (second_span.start.line, second_span.start.column)
                if first_pos >= second_pos:
                    continue
                intervening = False
                stage_groups = (filters, list(program.ast.sorts),
                                list(program.ast.aggregates), list(program.ast.reduces),
                                list(program.ast.conditional_pipelines))
                for group in stage_groups:
                    for candidate in group:
                        if getattr(candidate, "source", None) != first.result:
                            continue
                        span = source_span_of(candidate)
                        if span is None:
                            continue
                        pos = (span.start.line, span.start.column)
                        if first_pos < pos < second_pos:
                            intervening = True
                            break
                    if intervening:
                        break
                if intervening:
                    continue
            composed = _substitute_item(second.expr, first.expr)
            composed, folded = _fold(composed)
            maps[first_index] = MapOp(first.source, composed, second.result)
            fused_intermediates[second.result] = (first.source, first.result, first.expr)
            del maps[i]
            map_fusions += 1
            folds += int(folded)
            changed = True
            break
    # Identity maps are represented as zero-copy aliases at runtime. Keep the
    # semantic operation in the graph so downstream references remain valid.
    # Filter -> map is a common declarative pipeline. Keep the semantic graph
    # unchanged, but record a legal one-pass lowering when the filter result is
    # not observable. The runtime can then evaluate both stages while scanning
    # the original source exactly once. This is deliberately metadata rather
    # than a new source-level operation: semantics remain filter followed by map.
    filter_by_result = {f.result: f for f in filters}
    fused_pipelines = {}
    pipeline_fusions = 0
    all_consumers = (list(maps) + list(program.ast.sorts) + list(program.ast.aggregates) +
                     list(program.ast.reduces) + list(program.ast.conditional_pipelines))
    for m in maps:
        f = filter_by_result.get(m.source)
        if f is None or f.result in observed:
            continue
        # Fuse only when the filter has exactly this one downstream consumer.
        # Otherwise another consumer would still require the materialized
        # filtered collection.
        consumers = [consumer for consumer in all_consumers if consumer.source == f.result]
        if consumers != [m]:
            continue
        base = f.source
        fused_pipelines[m.result] = (base, (f,), (m,))
        pipeline_fusions += 1

    identity_aliases = {m.result: m.source for m in maps if _is_identity(m.expr)}
    # Terminal fusion extends one-pass execution across filter/map -> aggregate
    # chains.  The terminal is fused only when every intermediate has a single
    # consumer and is not externally observed.  This keeps the transformation
    # semantics-preserving while allowing longer declarative chains to become a
    # single execution strategy.
    fused_terminals = {}
    fused_terminal_intermediates = set()
    terminal_ops = [a for a in program.ast.aggregates
                    if a.operation in ("sum", "max", "min", "average", "avg")]
    for terminal in terminal_ops:
        chain_maps = []
        current = terminal.source
        map_by_result = {m.result: m for m in maps}
        while current in map_by_result:
            m = map_by_result[current]
            if m.result in observed:
                chain_maps = []
                break
            consumers = [c for c in (list(program.ast.aggregates) + list(program.ast.reduces) +
                                     list(program.ast.sorts) + list(program.ast.filters) +
                                     list(program.ast.conditional_pipelines) + list(maps))
                         if getattr(c, 'source', None) == m.result]
            if consumers != [terminal] and not (len(chain_maps) == 0 and consumers == [m]):
                # The first map may still have been rewritten by map fusion;
                # any additional consumer makes terminal fusion unsafe.
                break
            chain_maps.insert(0, m)
            current = m.source
            if len(chain_maps) > 8:
                break
        if chain_maps == [] and terminal.source in map_by_result:
            continue

        filter_chain = []
        filter_by_result = {f.result: f for f in filters}
        if current in filter_by_result:
            f = filter_by_result[current]
            if f.result in observed:
                continue
            consumers = [c for c in (list(maps) + list(program.ast.aggregates) +
                                     list(program.ast.reduces) + list(program.ast.sorts))
                         if getattr(c, 'source', None) == f.result]
            # The filter may feed the first fused map, or the terminal directly.
            if chain_maps:
                first_map = chain_maps[0]
                if consumers != [first_map]:
                    continue
            elif consumers != [terminal]:
                continue
            filter_chain = [f]
            current = f.source

        if not chain_maps and not filter_chain:
            continue
        fused_terminals[terminal.result] = (current, tuple(filter_chain), tuple(chain_maps), terminal)
        fused_terminal_intermediates.update(f.result for f in filter_chain)
        fused_terminal_intermediates.update(m.result for m in chain_maps)
        pipeline_fusions += 1

    program._optimization_record_materialization_boundaries = record_materialization_boundaries
    program._optimization_identity_aliases = identity_aliases
    program._optimization_fused_intermediates = fused_intermediates
    program._optimization_fused_pipelines = fused_pipelines
    program._optimization_fused_terminals = fused_terminals
    program._optimization_fused_terminal_intermediates = fused_terminal_intermediates
    identity_removed = len(identity_aliases)
    program.ast.maps = maps

    downstream_pressure = round(sum(d.downstream_pressure for d in getattr(program, "_record_fusion_decisions", [])), 3)
    downstream_fanout = sum(d.downstream_fanout for d in getattr(program, "_record_fusion_decisions", []))
    return OptimizationReport(folds, filter_fusions, map_fusions, pipeline_fusions, record_transform_fusions, identity_removed, record_transform_partial, record_transform_materialized, downstream_pressure, downstream_fanout)
