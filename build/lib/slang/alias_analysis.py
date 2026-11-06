from __future__ import annotations
from dataclasses import dataclass
from .memory_regions import MemoryRegion

@dataclass(frozen=True)
class AliasFact:
    left: str
    right: str
    relation: str  # must-alias | no-alias | may-alias
    reason: str


def classify(a: MemoryRegion, b: MemoryRegion) -> tuple[str, str]:
    if a.canonical == b.canonical:
        return "must-alias", "identical memory region"
    if a.root != b.root:
        return "no-alias", "different roots"
    if not a.overlaps(b):
        return "no-alias", "disjoint memory regions"
    return "may-alias", "regions overlap but identity cannot be proven"


def relation(a: MemoryRegion, b: MemoryRegion) -> str:
    """Return the conservative alias relation used by scheduling."""
    return classify(a, b)[0]


def analyze_regions(regions: list[tuple[str, MemoryRegion]]) -> tuple[AliasFact, ...]:
    facts = []
    for i, (left_name, left) in enumerate(regions):
        for right_name, right in regions[i + 1:]:
            relation, reason = classify(left, right)
            facts.append(AliasFact(left_name, right_name, relation, reason))
    return tuple(facts)


def analyze_execution_ir(execution_ir):
    regions = []
    for node in execution_ir.nodes:
        for region in node.memory_region_specs:
            regions.append((node.binding, region))
    # Deduplicate exact node/region pairs for stable output.
    unique = []
    seen = set()
    for item in regions:
        key = (item[0], item[1].canonical)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return analyze_regions(unique)


def format_alias_analysis(execution_ir) -> str:
    facts = analyze_execution_ir(execution_ir)
    lines = ["alias.analysis {"]
    if not facts:
        lines.append("  facts = none")
    else:
        for fact in facts:
            lines.append(f'  {fact.left} <-> {fact.right}: {fact.relation} ({fact.reason})')
    lines.append("  conservative = yes")
    lines.append("}")
    return "\n".join(lines)
