"""Deterministic semantic fusion planning for S-Lang 0.89.

Fusion is an ExecutionPlan candidate rather than backend-specific logic.  The
planner can expose both a complete one-pass fusion and a partial prefix fusion
for longer collection pipelines.  The cost model decides which legal form is
selected; unsupported native forms remain non-executable metadata.
"""
from __future__ import annotations
from dataclasses import dataclass

_ALLOWED = {"filter", "map"}
_TERMINALS = {"aggregate", "reduce"}
_MAX_FULL_FUSION_OPS = 3  # backend-independent planning cap for the first implementation

@dataclass(frozen=True)
class FusionGroup:
    nodes: tuple[str, ...]
    terminal: str
    strategy: str
    reason: str
    mode: str = "full"  # full | partial
    materializes: bool = False
    fused_prefix_length: int = 0

    @property
    def source(self) -> str:
        return self.nodes[0] if self.nodes else ""


def _legal(node) -> bool:
    return (
        node.pure and node.deterministic and node.reorderable
        and not node.effects and node.access == "read-only"
    )


def _strategy(kinds: list[str], terminal_kind: str, mode: str) -> str:
    prefix = "-".join(kinds)
    suffix = "reduce" if terminal_kind == "reduce" else "aggregate"
    if mode == "full":
        return f"fused-{prefix}-{suffix}"
    return f"fused-{prefix}-then-{suffix}"


def _chain_for_terminal(ir, terminal):
    by = ir.by_binding()
    current = terminal
    chain = [terminal.binding]
    while True:
        parents = [by[d] for d in current.dependencies if d in by]
        candidates = [p for p in parents if p.kind in _ALLOWED and _legal(p)]
        if len(candidates) != 1:
            break
        parent = candidates[0]
        consumers = [n for n in ir.nodes if parent.binding in n.dependencies]
        if len(consumers) != 1:
            break
        chain.append(parent.binding)
        current = parent
    return list(reversed(chain)), by


def find_fusion_groups(ir) -> tuple[FusionGroup, ...]:
    """Find deterministic full and partial legal collection fusion candidates."""
    groups: list[FusionGroup] = []
    for terminal in sorted((n for n in ir.nodes if n.kind in _TERMINALS), key=lambda n: n.binding):
        if not _legal(terminal):
            continue
        chain, by = _chain_for_terminal(ir, terminal)
        if len(chain) < 2:
            continue
        kinds = [by[name].kind for name in chain]
        if kinds[-1] not in _TERMINALS or not all(k in _ALLOWED for k in kinds[:-1]):
            continue

        # Full fusion candidate.  It is executable only when the backend has a
        # direct implementation for this bounded first-generation form.
        full_kinds = kinds[:-1]
        if len(full_kinds) <= _MAX_FULL_FUSION_OPS - 1:
            groups.append(FusionGroup(
                tuple(chain), terminal.binding,
                _strategy(full_kinds, terminal.kind, "full"),
                "legal pure deterministic collection chain can execute in one pass",
                mode="full", materializes=False, fused_prefix_length=len(full_kinds),
            ))

        # Partial fusion is useful for longer chains: fuse a prefix and keep a
        # materialized boundary before the terminal operation.  The longest
        # legal prefix is exposed as a deterministic alternative.
        if len(full_kinds) >= 2 and len(full_kinds) > _MAX_FULL_FUSION_OPS - 1:
            prefix_len = _MAX_FULL_FUSION_OPS - 1
            prefix_kinds = kinds[:prefix_len]
            groups.append(FusionGroup(
                tuple(chain), terminal.binding,
                _strategy(prefix_kinds, terminal.kind, "partial"),
                "legal prefix fusion reduces intermediate materialization while retaining a boundary before the terminal",
                mode="partial", materializes=True, fused_prefix_length=prefix_len,
            ))
    return tuple(groups)
