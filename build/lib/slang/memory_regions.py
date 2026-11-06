from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MemoryRegion:
    """Structured symbolic memory location used by compiler analyses."""
    root: str
    selector: str | None = None
    path: tuple[str, ...] = ()
    scope: str = "root"  # root | collection | element | field

    @property
    def canonical(self) -> str:
        out = self.root
        if self.selector is not None:
            out += f"[*]" if self.selector == "*" else f"[{self.selector}]"
        if self.path:
            out += "." + ".".join(self.path)
        return out

    @classmethod
    def parse(cls, text: str) -> "MemoryRegion":
        root, rest = text, ""
        if "[*]" in text:
            root, rest = text.split("[*]", 1)
            selector = "*"
            scope = "element" if rest.startswith(".") else "collection"
        else:
            selector = None
            scope = "root"
        path = tuple(x for x in rest.lstrip(".").split(".") if x)
        if path:
            scope = "field"
        return cls(root=root, selector=selector, path=path, scope=scope)

    def overlaps(self, other: "MemoryRegion") -> bool:
        if self.root != other.root:
            return False
        if self.selector != other.selector:
            # Unknown/non-indexed roots are conservatively overlapping.
            return self.selector is None or other.selector is None
        a, b = self.path, other.path
        return a[:len(b)] == b or b[:len(a)] == a

def parse_regions(values):
    return tuple(MemoryRegion.parse(v) for v in values)
