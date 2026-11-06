"""Determinism invariants for mixed plan/reference execution.

The compiler and runtime must preserve observable semantics when a legal
execution is split into plan-runtime and reference-runtime regions.  This
module provides a small, backend-neutral contract for that invariant.
"""
from __future__ import annotations
from dataclasses import is_dataclass, asdict


def _freeze(value, _seen=None):
    """Return a stable, recursively comparable representation."""
    _seen = set() if _seen is None else _seen
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if callable(value):
        return ("callable", getattr(value, "name", None) or getattr(value, "__name__", type(value).__name__))
    marker = id(value)
    if marker in _seen:
        return ("cycle", type(value).__name__)
    _seen.add(marker)
    if isinstance(value, bytes):
        return ("bytes", value.hex())
    if isinstance(value, dict):
        return ("dict", tuple(sorted((str(k), _freeze(v, _seen)) for k, v in value.items())))
    if isinstance(value, (list, tuple)):
        return ("seq", tuple(_freeze(v, _seen) for v in value))
    if isinstance(value, set):
        return ("set", tuple(sorted((_freeze(v, _seen) for v in value), key=repr)))
    if is_dataclass(value):
        return (type(value).__name__, _freeze(asdict(value), _seen))
    if hasattr(value, "unit") and hasattr(value, "value"):
        return (type(value).__name__, _freeze(getattr(value, "value"), _seen), str(getattr(value, "unit")))
    if hasattr(value, "__dict__"):
        return (type(value).__name__, _freeze(vars(value), _seen))
    return (type(value).__name__, repr(value))


def observable_snapshot(module):
    """Capture the language-visible mutable state, excluding executor internals."""
    return _freeze({
        "bindings": getattr(module, "_bindings", {}) or {},
        "collections": getattr(module, "_collections", {}) or {},
        "states": getattr(module, "_states", {}) or {},
        "entities": getattr(module, "entities", {}) or {},
        "data_result_name": getattr(module, "_data_result_name", None),
        "data_result": getattr(module, "_data_result", None),
    })


def validate_segment_determinism(selected_plan, ir=None):
    """Validate static invariants required for segmentation-independent execution."""
    steps = selected_plan.steps
    selected_nodes = tuple(step.node for step in steps)
    covered_nodes = tuple(node for segment in selected_plan.segments for node in segment.nodes)
    if selected_nodes != covered_nodes:
        raise ValueError("determinism violation: segmentation changes selected node order")
    if len(set(covered_nodes)) != len(covered_nodes):
        raise ValueError("determinism violation: a node occurs in multiple segments")

    by_node = {getattr(node, "binding", None): node for node in getattr(ir, "nodes", ())} if ir is not None else {}
    for step in steps:
        node = by_node.get(step.node)
        if node is not None and not getattr(node, "deterministic", True):
            raise ValueError(f"determinism violation: node {step.node!r} is nondeterministic")
        if step.parallelism != "sequential" and step.ordering not in {"dependency-ordered", "source-order"}:
            raise ValueError(
                f"determinism violation: strategy {step.strategy!r} has unordered parallel execution"
            )

    # Segment transitions must themselves be monotonic.  Independent nodes may
    # be parallelized, but the segment graph cannot introduce a new ordering.
    indices = {node: i for i, node in enumerate(covered_nodes)}
    for segment in selected_plan.segments:
        if tuple(sorted(segment.nodes, key=indices.__getitem__)) != segment.nodes:
            raise ValueError(f"determinism violation: segment {segment.index} reorders nodes")
    return True
