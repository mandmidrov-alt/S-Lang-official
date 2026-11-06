from __future__ import annotations
from dataclasses import dataclass
from .alias_analysis import classify

@dataclass(frozen=True)
class ConflictEdge:
    before: str
    after: str
    relation: str
    reason: str


def _writes(node):
    return bool(node.memory_writes) or node.access == 'write'


def _regions_conflict(a, b):
    if a.kind == 'state:read' and b.kind == 'state:read':
        return False, 'read/read'
    if not a.memory_region_specs or not b.memory_region_specs:
        return False, 'no-region'
    aw, bw = _writes(a), _writes(b)
    if not aw and not bw:
        # Preserve the conservative rule used by 0.62: a whole-collection
        # view conflicts with a narrower overlapping view even for reads.
        for x in a.memory_region_specs:
            for y in b.memory_region_specs:
                rel, why = classify(x, y)
                if rel != 'no-alias' and (x.scope == 'collection' or y.scope == 'collection'):
                    return True, 'whole-collection overlap'
        return False, 'read/read'
    worst = 'no-alias'
    reason = 'disjoint memory regions'
    for x in a.memory_region_specs:
        for y in b.memory_region_specs:
            rel, why = classify(x, y)
            if rel == 'must-alias':
                return True, why
            if rel == 'may-alias':
                worst, reason = rel, why
    return worst != 'no-alias', reason


def build_conflict_graph(ir):
    edges = []
    nodes = list(ir.nodes)
    for i, before in enumerate(nodes):
        for after in nodes[i + 1:]:
            conflict, reason = _regions_conflict(before, after)
            # Explicit state read/write tuples can cover scalar state even when
            # no MemoryRegion object was attached.
            if not conflict:
                # Scalar state accesses have no MemoryRegion object, but their
                # read/write names are still concrete alias information.
                if before.memory_writes and after.memory_writes:
                    conflict = bool(set(before.memory_writes) & set(after.memory_writes))
                    reason = 'state write/write overlap' if conflict else reason
                elif before.memory_reads and after.memory_writes:
                    conflict = bool(set(before.memory_reads) & set(after.memory_writes))
                    reason = 'state read/write overlap' if conflict else reason
                elif after.memory_reads and before.memory_writes:
                    conflict = bool(set(before.memory_writes) & set(after.memory_reads))
                    reason = 'state write/read overlap' if conflict else reason
            if conflict:
                relation = 'may-alias'
                if before.memory_region_specs and after.memory_region_specs:
                    rels = [classify(x, y)[0] for x in before.memory_region_specs for y in after.memory_region_specs]
                    relation = 'must-alias' if 'must-alias' in rels else 'may-alias'
                edges.append(ConflictEdge(before.binding, after.binding, relation, reason))
    return tuple(edges)


def format_conflict_graph(ir):
    edges = build_conflict_graph(ir)
    lines = ['conflict.graph {']
    if not edges:
        lines.append('  edges = none')
    else:
        for e in edges:
            lines.append(f'  {e.before} -> {e.after}: {e.relation} ({e.reason})')
    lines.append(f'  edges_count = {len(edges)}')
    lines.append('  conservative = yes')
    lines.append('}')
    return '\n'.join(lines)


def conflict_pairs(ir):
    """Return unordered pairs that must not execute concurrently.

    This is a direct safety boundary for parallel scheduling.  It is intentionally
    separate from the dependency graph: a future scheduler/backend may construct
    a ready set without rebuilding dependency edges, but it must still consult
    this predicate before granting parallel execution.
    """
    return frozenset(
        tuple(sorted((edge.before, edge.after)))
        for edge in build_conflict_graph(ir)
    )


def group_is_conflict_free(ir, names):
    names = tuple(names)
    if len(names) < 2:
        return True
    pairs = conflict_pairs(ir)
    return all(
        tuple(sorted((a, b))) not in pairs
        for i, a in enumerate(names)
        for b in names[i + 1:]
    )
