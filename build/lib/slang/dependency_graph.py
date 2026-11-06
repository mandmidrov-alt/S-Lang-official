from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR
from .conflict_graph import build_conflict_graph

@dataclass(frozen=True)
class DependencyEdge:
    before: str
    after: str
    kind: str  # data | memory | effect | explicit
    reason: str

@dataclass(frozen=True)
class DependencyGraph:
    edges: tuple[DependencyEdge, ...]

    @property
    def by_kind(self):
        out = {k: [] for k in ("data", "memory", "effect", "explicit")}
        for edge in self.edges:
            out.setdefault(edge.kind, []).append(edge)
        return {k: tuple(v) for k, v in out.items()}

    @property
    def nodes(self):
        out = set()
        for e in self.edges:
            out.add(e.before); out.add(e.after)
        return tuple(sorted(out))

def _add(edges, seen, before, after, kind, reason):
    if before == after:
        return
    key=(before, after, kind)
    if key in seen:
        return
    seen.add(key)
    edges.append(DependencyEdge(before, after, kind, reason))

def _dependency_kind(ir, before, after):
    b = ir.by_binding().get(before)
    a = ir.by_binding().get(after)
    if b is None or a is None:
        return "data", "semantic dependency"
    # Observable effects already have source-order dependencies in ExecutionIR.
    if (b.effects or b.order_sensitive) and (a.effects or a.order_sensitive):
        return "effect", "ordered effect dependency"
    if b.kind == "state:read" or a.kind in {"state:init", "state:set"}:
        return "effect", "state dependency"
    return "data", "produced-value dependency"

def build_dependency_graph(ir: ExecutionIR) -> DependencyGraph:
    edges=[]; seen=set()
    bindings={n.binding for n in ir.nodes}

    # ExecutionIR dependencies are semantic/data dependencies. Effectful state
    # and I/O dependencies are classified separately so the unified graph can
    # expose why a scheduler edge exists.
    for node in ir.nodes:
        for dep in node.dependencies:
            if dep in bindings:
                kind, reason = _dependency_kind(ir, dep, node.binding)
                _add(edges, seen, dep, node.binding, kind, reason)

    # AliasAnalysis -> ConflictGraph -> unified dependency graph.
    for edge in build_conflict_graph(ir):
        _add(edges, seen, edge.before, edge.after, "memory", f"{edge.relation}: {edge.reason}")

    # Explicit dependencies are reserved for a future source-level dependency
    # declaration. The graph supports the category without inventing one in the
    # current language, where no such syntax exists yet.
    edges.sort(key=lambda e: (e.before, e.after, e.kind))
    return DependencyGraph(tuple(edges))

def format_dependency_graph(graph: DependencyGraph) -> str:
    lines=["dependency.graph {"]
    if not graph.edges:
        lines.append("  edges = none")
    else:
        for e in graph.edges:
            lines.append(f"  {e.before} -> {e.after}: {e.kind} ({e.reason})")
    counts={k: len(graph.by_kind.get(k, ())) for k in ("data","memory","effect","explicit")}
    for k in ("data","memory","effect","explicit"):
        lines.append(f"  {k}_edges = {counts[k]}")
    lines.append(f"  edges_count = {len(graph.edges)}")
    lines.append("  explicit_dependencies = not-yet-implemented")
    lines.append("  conservative_memory = yes")
    lines.append("}")
    return "\n".join(lines)
