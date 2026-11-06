"""Static runtime-capability audit for S-Lang execution plans.

The audit is intentionally separate from execution.  It answers one question:
can the selected plan be executed by the unified plan-runtime, and if not,
which exact plan nodes require the reference runtime and why?
"""
from __future__ import annotations
from dataclasses import dataclass


# These are the semantic node kinds for which runtime.py has a direct dispatch.
SUPPORTED_KINDS = frozenset({
    "function", "property", "binding", "filter", "sort", "map", "aggregate", "reduce",
    "conditional-pipeline", "state:init", "state:set", "state:read",
    "sequence", "goal:transition", "goal:select", "goal:path", "goal:satisfy",
    "physics.gravity", "effect:show",
})

def runtime_strategy_supported(kind: str, strategy: str) -> bool:
    """Return whether a strategy has a direct unified-runtime contract.

    This is deliberately strategy-aware: semantic legality and runtime
    executability are separate properties.  The planner uses this predicate
    to prefer executable strategies while retaining a semantic fallback when
    no executable strategy exists.
    """
    generic_kinds = {
        "function", "property", "binding", "effect:show",
        "state:init", "state:set", "state:read",
    }
    if strategy == "generic":
        return kind in generic_kinds
    if strategy == "parallel-generic":
        return kind in {"binding", "effect:show", "state:read"}
    if strategy in {"scan-filter", "parallel-filter"}:
        return kind == "filter"
    if strategy in {"sequential-map", "parallel-map"}:
        return kind == "map"
    if strategy in {"stable-sort", "parallel-stable-sort"}:
        return kind == "sort"
    if strategy == "sequential-aggregate":
        return kind == "aggregate"
    if strategy == "sequential-reduce":
        return kind == "reduce"
    if strategy == "conditional-pipeline":
        return kind == "conditional-pipeline"
    if strategy == "state-transition":
        return kind in {"sequence", "goal:transition"}
    if strategy == "goal-scan-select":
        return kind == "goal:select"
    if strategy in {"graph-shortest-path", "bidirectional-dijkstra", "a-star-landmark"}:
        return kind == "goal:path"
    if strategy in {"constraint-propagation", "constraint-enumeration"}:
        return kind == "goal:satisfy"
    if strategy == "physics-domain":
        return kind == "physics.gravity"
    if strategy.startswith("fused-"):
        return kind in {"map", "reduce", "aggregate"}
    return False



@dataclass(frozen=True)
class RuntimeCapability:
    node: str
    kind: str
    strategy: str
    supported: bool
    mode: str
    reason: str


@dataclass(frozen=True)
class RuntimeCapabilityReport:
    entries: tuple[RuntimeCapability, ...]
    unified_supported: bool
    fallback_required: bool
    fallback_nodes: tuple[str, ...]

    @property
    def supported_nodes(self) -> int:
        return sum(1 for entry in self.entries if entry.supported)

    @property
    def total_nodes(self) -> int:
        return len(self.entries)


def _reason(kind: str, strategy: str) -> str:
    if kind not in SUPPORTED_KINDS:
        return f"semantic node kind '{kind}' has no unified plan-runtime dispatch"
    if not runtime_strategy_supported(kind, strategy):
        return f"selected strategy '{strategy}' is semantically legal but has no unified runtime contract"
    return "direct unified plan-runtime implementation is available"


def audit_runtime_capability(pipeline) -> RuntimeCapabilityReport:
    """Audit every selected plan node without executing the program."""
    by = pipeline.optimized_ir.by_binding()
    entries = []
    for step in pipeline.selected_execution_plan.steps:
        node = by[step.node]
        supported = node.kind in SUPPORTED_KINDS and runtime_strategy_supported(node.kind, step.strategy)
        entries.append(RuntimeCapability(
            node=step.node,
            kind=node.kind,
            strategy=step.strategy,
            supported=supported,
            mode="plan-runtime" if supported else "reference-interpreter",
            reason=_reason(node.kind, step.strategy),
        ))
    fallback = tuple(entry.node for entry in entries if not entry.supported)
    return RuntimeCapabilityReport(
        entries=tuple(entries),
        unified_supported=bool(entries) and not fallback,
        fallback_required=bool(fallback),
        fallback_nodes=fallback,
    )


def format_runtime_capability(report: RuntimeCapabilityReport) -> str:
    lines = ["runtime.capability {"]
    lines.append(f"  unified_supported = {'yes' if report.unified_supported else 'no'}")
    lines.append(f"  fallback_required = {'yes' if report.fallback_required else 'no'}")
    lines.append(f"  supported_nodes = {report.supported_nodes}/{report.total_nodes}")
    for entry in report.entries:
        status = "plan-runtime" if entry.supported else "reference-interpreter"
        lines.append(f"  {entry.node}: {status} kind={entry.kind} strategy={entry.strategy}")
        lines.append(f"    why = {entry.reason}")
    if report.fallback_nodes:
        lines.append("  fallback_nodes = " + ", ".join(report.fallback_nodes))
    else:
        lines.append("  fallback_nodes = none")
    lines.append("  model = deterministic-static-runtime-capability")
    lines.append("}")
    return "\n".join(lines)
