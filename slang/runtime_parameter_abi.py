"""Runtime validation table for persisted S-Lang parameter ABI descriptors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeParameterDescriptor:
    binding: str
    kind: str
    value_type: str
    byte_size: int
    format: str
    encoding: str
    seed: int

    def as_tuple(self) -> tuple[str, str, str, int, str, str, int]:
        return (self.binding, self.kind, self.value_type, self.byte_size, self.format, self.encoding, self.seed)


def _expected_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "json"


def build_runtime_parameter_table(artifact) -> dict[str, RuntimeParameterDescriptor]:
    """Build a checked runtime descriptor table from a persisted artifact."""
    import json
    materialized = {b: (k, canonical, int(seed)) for b, k, canonical, seed in artifact.parameter_materialization}
    table: dict[str, RuntimeParameterDescriptor] = {}
    for binding, kind, value_type, byte_size, fmt, encoding in artifact.parameter_abi_descriptors:
        if binding not in materialized:
            raise ValueError(f"runtime parameter descriptor has no materialization: {binding}")
        materialized_kind, canonical, seed = materialized[binding]
        if kind != materialized_kind:
            raise ValueError(f"runtime parameter kind mismatch for {binding}")
        if fmt != "canonical-json" or encoding != "utf8":
            raise ValueError(f"unsupported runtime parameter ABI for {binding}")
        actual_size = len(canonical.encode("utf-8"))
        if byte_size != actual_size:
            raise ValueError(f"runtime parameter byte-size mismatch for {binding}")
        actual_type = _expected_type(json.loads(canonical))
        if value_type != actual_type:
            raise ValueError(f"runtime parameter type mismatch for {binding}")
        expected_seed = int(__import__("hashlib").sha256(canonical.encode("utf-8")).hexdigest()[:16], 16) & ((1 << 63) - 1)
        if seed != expected_seed:
            raise ValueError(f"runtime parameter seed mismatch for {binding}")
        if seed < 0 or seed >= (1 << 63):
            raise ValueError(f"runtime parameter seed out of ABI range for {binding}")
        table[binding] = RuntimeParameterDescriptor(binding, kind, value_type, byte_size, fmt, encoding, seed)
    if set(table) != set(materialized):
        raise ValueError("runtime parameter descriptor table does not match materialization")
    return table


def validate_runtime_parameter(artifact, binding: str, *, kind: str | None = None, value_type: str | None = None, byte_size: int | None = None) -> RuntimeParameterDescriptor:
    table = build_runtime_parameter_table(artifact)
    descriptor = table.get(binding)
    if descriptor is None and "#" in binding:
        descriptor = table.get(binding.split("#", 1)[0])
    if descriptor is None:
        raise ValueError(f"runtime parameter descriptor not found: {binding}")
    if kind is not None and descriptor.kind != kind:
        raise ValueError(f"runtime parameter kind mismatch for {binding}")
    if value_type is not None and descriptor.value_type != value_type:
        raise ValueError(f"runtime parameter type mismatch for {binding}")
    if byte_size is not None and descriptor.byte_size != byte_size:
        raise ValueError(f"runtime parameter byte-size mismatch for {binding}")
    return descriptor


def materialize_runtime_parameter(artifact, binding: str, *, kind: str | None = None) -> int:
    """Return the validated opaque runtime handle for a persisted parameter."""
    return validate_runtime_parameter(artifact, binding, kind=kind).seed


def validate_runtime_call_parameter(
    artifact,
    binding: str,
    *,
    operation_kind: str,
    descriptor_seed: int,
    value_type: str | None = None,
    byte_size: int | None = None,
) -> RuntimeParameterDescriptor:
    """Validate a materialized parameter immediately before a runtime call."""
    descriptor = validate_runtime_parameter(
        artifact,
        binding,
        kind=operation_kind,
        value_type=value_type,
        byte_size=byte_size,
    )
    if int(descriptor_seed) != descriptor.seed:
        raise ValueError(f"runtime call parameter seed mismatch for {binding}")
    return descriptor
