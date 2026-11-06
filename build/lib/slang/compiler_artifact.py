"""Stable compiler artifact boundary for S-Lang 1.14.x.

The artifact is a deterministic, backend-neutral snapshot of the semantic
compiler pipeline. It deliberately contains contracts and fingerprints rather
than Python object serialization, so a backend can inspect/cache a compilation
without re-running semantic analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from dataclasses import fields, is_dataclass
from . import ast as ast_module


ARTIFACT_VERSION = "7"


def _json_default(value: Any):
    if hasattr(value, "__dict__"):
        return {k: getattr(value, k) for k in sorted(value.__dict__)}
    if hasattr(value, "name"):
        return getattr(value, "name")
    return repr(value)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


def _encode_payload(value: Any) -> Any:
    """Encode the semantic AST into deterministic JSON-safe data.

    Only S-Lang AST dataclasses are accepted as structured values. This keeps
    artifact loading explicit and prevents arbitrary Python object execution.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        return {"__tuple__": [_encode_payload(x) for x in value]}
    if isinstance(value, list):
        return {"__list__": [_encode_payload(x) for x in value]}
    if isinstance(value, dict):
        return {"__dict__": [[_encode_payload(k), _encode_payload(v)] for k, v in sorted(value.items(), key=lambda item: repr(item[0]))]}
    if type(value).__module__ == "slang.core" and type(value).__name__ == "Quantity":
        return {"__quantity__": [float(value.value), value.unit]}
    if is_dataclass(value):
        cls = type(value)
        if cls.__module__ != ast_module.__name__:
            raise TypeError(f"artifact payload does not allow dataclass {cls.__module__}.{cls.__name__}")
        return {
            "__type__": cls.__name__,
            "fields": {field.name: _encode_payload(getattr(value, field.name)) for field in fields(value)},
        }
    raise TypeError(f"artifact payload cannot encode value of type {type(value).__name__}")


def _decode_payload(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if not isinstance(value, dict):
        raise ValueError("invalid artifact payload value")
    if "__tuple__" in value:
        return tuple(_decode_payload(x) for x in value["__tuple__"])
    if "__list__" in value:
        return [_decode_payload(x) for x in value["__list__"]]
    if "__dict__" in value:
        return {_decode_payload(k): _decode_payload(v) for k, v in value["__dict__"]}
    if "__quantity__" in value:
        from .core import Quantity
        raw = value["__quantity__"]
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError("invalid Quantity artifact payload")
        return Quantity(raw[0], raw[1])
    type_name = value.get("__type__")
    if type_name is not None:
        cls = getattr(ast_module, type_name, None)
        if cls is None or not is_dataclass(cls):
            raise ValueError(f"unsupported artifact AST type '{type_name}'")
        raw_fields = value.get("fields", {})
        if not isinstance(raw_fields, dict):
            raise ValueError(f"invalid fields for artifact AST type '{type_name}'")
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(raw_fields) - allowed)
        if unknown:
            raise ValueError(f"unknown fields for artifact AST type '{type_name}': {', '.join(unknown)}")
        kwargs = {name: _decode_payload(raw_fields[name]) for name in raw_fields}
        return cls(**kwargs)
    raise ValueError("invalid artifact payload object")


def _ir_contract(ir) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "binding": n.binding,
                "kind": n.kind,
                "result": n.result,
                "dependencies": list(n.dependencies),
                "external_sources": list(n.external_sources),
                "pure": n.pure,
                "deterministic": n.deterministic,
                "access": n.access,
                "order_sensitive": n.order_sensitive,
                "effects": list(n.effects),
                "input_type": n.input_type,
                "output_type": n.output_type,
                "input_schema": repr(n.input_schema),
                "output_schema": repr(n.output_schema),
                "record_field_provenance": [
                    [name, list(fields), certainty]
                    for name, fields, certainty in n.record_field_provenance
                ],
            }
            for n in ir.nodes
        ],
        "topological_order": list(ir.topological_order()),
    }


@dataclass(frozen=True)
class CompilerArtifact:
    """Backend-neutral deterministic snapshot of one compilation pipeline."""

    artifact_version: str
    source_ir: dict[str, Any]
    optimized_ir: dict[str, Any]
    type_contract: tuple[tuple[str, str | None, str | None], ...]
    schema_contract: tuple[tuple[str, str, str], ...]
    strategy_contract: tuple[tuple[str, str], ...]
    effect_contract: tuple[tuple[str, tuple[str, ...]], ...]
    capability_contract: object
    execution_profile: str
    fingerprint: str
    backend_payload: dict[str, Any] | None = None
    selected_execution_plan: dict[str, Any] | None = None
    operation_contract: tuple[tuple[str, str, Any], ...] = ()
    parameter_materialization: tuple[tuple[str, str, str, str], ...] = ()
    parameter_abi_descriptors: tuple[tuple[str, str, str, int, str, str], ...] = ()

    def manifest(self) -> dict[str, Any]:
        """Return JSON-safe deterministic metadata for tooling and caching."""
        return {
            "artifact_version": self.artifact_version,
            "source_ir": self.source_ir,
            "optimized_ir": self.optimized_ir,
            "type_contract": [list(x) for x in self.type_contract],
            "schema_contract": [list(x) for x in self.schema_contract],
            "strategy_contract": [list(x) for x in self.strategy_contract],
            "effect_contract": [[name, list(effects)] for name, effects in self.effect_contract],
            "capability_contract": self.capability_contract,
            "execution_profile": self.execution_profile,
            "fingerprint": self.fingerprint,
            "backend_payload": self.backend_payload,
            "selected_execution_plan": self.selected_execution_plan,
            "operation_contract": [[binding, kind, params] for binding, kind, params in self.operation_contract],
            "parameter_materialization": [list(x) for x in self.parameter_materialization],
            "parameter_abi_descriptors": [list(x) for x in self.parameter_abi_descriptors],
        }

    def to_json(self) -> str:
        return _canonical(self.manifest())

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "CompilerArtifact":
        if not isinstance(manifest, dict):
            raise ValueError("compiler artifact manifest must be an object")
        if manifest.get("artifact_version") != ARTIFACT_VERSION:
            raise ValueError(
                f"unsupported compiler artifact version {manifest.get('artifact_version')!r}; expected {ARTIFACT_VERSION!r}"
            )
        required = (
            "source_ir", "optimized_ir", "type_contract", "schema_contract",
            "strategy_contract", "effect_contract", "capability_contract",
            "execution_profile", "fingerprint", "backend_payload", "selected_execution_plan", "operation_contract", "parameter_materialization", "parameter_abi_descriptors",
        )
        missing = [name for name in required if name not in manifest]
        if missing:
            raise ValueError("compiler artifact manifest is missing: " + ", ".join(missing))
        payload = dict(manifest)
        expected = payload.pop("fingerprint")
        actual = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
        if expected != actual:
            raise ValueError("compiler artifact fingerprint mismatch")
        backend_payload = payload["backend_payload"]
        selected_execution_plan = payload["selected_execution_plan"]
        operation_contract = payload["operation_contract"]
        parameter_materialization = payload["parameter_materialization"]
        parameter_abi_descriptors = payload["parameter_abi_descriptors"]
        if not isinstance(operation_contract, list):
            raise ValueError("invalid compiler artifact operation contract")
        if not isinstance(parameter_materialization, list):
            raise ValueError("invalid compiler artifact parameter materialization")
        if not isinstance(parameter_abi_descriptors, list):
            raise ValueError("invalid compiler artifact parameter ABI descriptors")
        normalized_operations = []
        for entry in operation_contract:
            if not isinstance(entry, list) or len(entry) != 3:
                raise ValueError("invalid compiler artifact operation contract entry")
            normalized_operations.append((str(entry[0]), str(entry[1]), entry[2]))
        normalized_materialization = []
        for entry in parameter_materialization:
            if not isinstance(entry, list) or len(entry) != 4:
                raise ValueError("invalid compiler artifact parameter materialization entry")
            normalized_materialization.append(tuple(str(x) for x in entry))
        normalized_descriptors = []
        for entry in parameter_abi_descriptors:
            if not isinstance(entry, list) or len(entry) != 6:
                raise ValueError("invalid compiler artifact parameter ABI descriptor")
            binding, kind, value_type, byte_size, fmt, encoding = entry
            if not isinstance(byte_size, int) or byte_size < 0:
                raise ValueError("invalid compiler artifact parameter ABI descriptor size")
            normalized_descriptors.append((str(binding), str(kind), str(value_type), byte_size, str(fmt), str(encoding)))
        if selected_execution_plan is not None:
            _validate_selected_execution_plan(selected_execution_plan)
        if backend_payload is not None:
            if not isinstance(backend_payload, dict) or "ast" not in backend_payload:
                raise ValueError("invalid compiler artifact backend payload")
            _decode_payload(backend_payload["ast"])
        return cls(
            artifact_version=payload["artifact_version"],
            source_ir=payload["source_ir"],
            optimized_ir=payload["optimized_ir"],
            type_contract=tuple(tuple(x) for x in payload["type_contract"]),
            schema_contract=tuple(tuple(x) for x in payload["schema_contract"]),
            strategy_contract=tuple(tuple(x) for x in payload["strategy_contract"]),
            effect_contract=tuple((x[0], tuple(x[1])) for x in payload["effect_contract"]),
            capability_contract=payload["capability_contract"],
            execution_profile=payload["execution_profile"],
            fingerprint=expected,
            backend_payload=backend_payload,
            selected_execution_plan=selected_execution_plan,
            operation_contract=tuple(normalized_operations),
            parameter_materialization=tuple(normalized_materialization),
            parameter_abi_descriptors=tuple(normalized_descriptors),
        )

    @classmethod
    def from_json(cls, text: str) -> "CompilerArtifact":
        try:
            manifest = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid compiler artifact JSON") from exc
        return cls.from_manifest(manifest)

    def backend_ast(self):
        if not self.backend_payload or "ast" not in self.backend_payload:
            raise ValueError("compiler artifact has no backend AST payload")
        return _decode_payload(self.backend_payload["ast"])


def _operation_contract(module) -> tuple[tuple[str, str, Any], ...]:
    """Persist operation parameters needed by concrete backend/runtime lowering."""
    if module is None:
        return ()
    entries = []
    def add(result, kind, params):
        entries.append((str(result), str(kind), _encode_payload(params)))
    for op in getattr(module, "filters", ()):
        add(op.result, "filter", {"source": op.source, "predicate": op.predicate.expr})
    for op in getattr(module, "sorts", ()):
        add(op.result, "sort", {"source": op.source, "expr": op.spec.expr, "ascending": op.spec.ascending})
    for op in getattr(module, "maps", ()):
        add(op.result, "map", {"source": op.source, "expr": op.expr})
    for op in getattr(module, "aggregates", ()):
        add(op.result, "aggregate", {"source": op.source, "operation": op.operation, "expr": op.expr})
    for op in getattr(module, "reduces", ()):
        add(op.result, "reduce", {"source": op.source, "initial": op.initial, "expr": op.expr})
    for op in getattr(module, "sequences", ()):
        add(op.result, "sequence", {"initial": op.initial, "steps": op.steps, "expr": op.expr, "until": op.until, "target": op.target, "candidates": op.candidates, "constraint": op.constraint, "constraints": op.constraints})
    for op in getattr(module, "goals", ()):
        add(op.result, "goal:select", {"source": op.source, "predicate": op.predicate, "key": op.key, "direction": op.direction})
    for op in getattr(module, "path_goals", ()):
        add(op.result, "goal:path", {"source": op.source, "start": op.start, "end": op.end, "objective": op.objective})
    for op in getattr(module, "satisfy_goals", ()):
        add(op.result, "goal:satisfy", {"variables": op.variables, "constraints": op.constraints})
    for op in getattr(module, "simulations", ()):
        add(op.target, "physics.gravity", {"target": op.target, "attractor": op.attractor, "duration": op.duration, "step": op.step})
    return tuple(sorted(entries, key=lambda x: (x[0], x[1], _canonical(x[2]))))


def _parameter_materialization_contract(operation_contract) -> tuple[tuple[str, str, str, str], ...]:
    """Create deterministic, ABI-ready materialization records for operation parameters."""
    records = []
    for binding, kind, params in operation_contract:
        canonical = _canonical(params)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        # Keep a signed-safe 63-bit seed for MLIR i64 constants. The canonical
        # payload remains persisted alongside it, so the seed is only the
        # deterministic ABI materialization key, not the payload itself.
        seed = str(int(digest[:16], 16) & ((1 << 63) - 1))
        records.append((str(binding), str(kind), canonical, seed))
    return tuple(sorted(records, key=lambda x: (x[0], x[1], x[2])))



def _parameter_abi_descriptor_contract(parameter_materialization) -> tuple[tuple[str, str, str, int, str, str], ...]:
    """Describe the exact persisted parameter ABI representation."""
    records = []
    for binding, kind, canonical, seed in parameter_materialization:
        try:
            value = json.loads(canonical)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid canonical parameter payload") from exc
        if value is None:
            value_type = "null"
        elif isinstance(value, bool):
            value_type = "bool"
        elif isinstance(value, int) and not isinstance(value, bool):
            value_type = "int"
        elif isinstance(value, float):
            value_type = "float"
        elif isinstance(value, str):
            value_type = "text"
        elif isinstance(value, list):
            value_type = "list"
        elif isinstance(value, dict):
            value_type = "object"
        else:
            value_type = "json"
        byte_size = len(canonical.encode("utf-8"))
        records.append((str(binding), str(kind), value_type, byte_size, "canonical-json", "utf8"))
    return tuple(sorted(records, key=lambda x: (x[0], x[1], x[2], x[3])))

def _selected_execution_plan_contract(plan) -> dict[str, Any]:
    if plan is None:
        return None
    return {
        "schema": "slang-selected-execution-plan-1",
        "deterministic": bool(plan.deterministic),
        "backend": plan.backend,
        "execution_profile": {
            "memory_budget": plan.execution_profile.memory_budget,
            "cpu_cores": plan.execution_profile.cpu_cores,
            "allow_parallelism": plan.execution_profile.allow_parallelism,
            "materialization_cost": plan.execution_profile.materialization_cost,
            "memory_cost": plan.execution_profile.memory_cost,
        },
        "steps": [
            {
                "level": s.level, "node": s.node, "strategy": s.strategy,
                "profile": s.profile, "score": s.score,
                "alternatives": list(s.alternatives), "memory_model": s.memory_model,
                "ordering": s.ordering, "parallelism": s.parallelism,
                "materialization": s.materialization, "execution_mode": s.execution_mode,
                "input_type": s.input_type, "output_type": s.output_type,
                "type_contracts": [list(x) for x in s.type_contracts],
            } for s in plan.steps
        ],
        "segments": [
            {
                "index": s.index, "mode": s.mode, "levels": list(s.levels),
                "nodes": list(s.nodes), "strategies": list(s.strategies),
                "entry_nodes": list(s.entry_nodes), "exit_nodes": list(s.exit_nodes),
                "data_contract": _json_safe_contract(s.data_contract),
                "execution_mode": s.execution_mode,
            } for s in plan.segments
        ],
        "execution_regions": [
            {"index": r.index, "mode": r.mode, "levels": list(r.levels),
             "nodes": list(r.nodes), "strategies": list(r.strategies)}
            for r in plan.execution_regions
        ],
        "record_plan": _json_safe_contract(plan.record_plan),
    }


def _json_safe_contract(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (tuple, list)):
        return [_json_safe_contract(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _json_safe_contract(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if is_dataclass(value):
        return {field.name: _json_safe_contract(getattr(value, field.name)) for field in fields(value)}
    return repr(value)


def _validate_selected_execution_plan(value):
    if not isinstance(value, dict) or value.get("schema") != "slang-selected-execution-plan-1":
        raise ValueError("invalid selected execution plan artifact payload")
    for key in ("steps", "segments", "execution_regions"):
        if not isinstance(value.get(key), list):
            raise ValueError(f"invalid selected execution plan field '{key}'")


def build_compiler_artifact(pipeline, module=None) -> CompilerArtifact:
    """Create a deterministic artifact from an already compiled pipeline."""
    source_ir = _ir_contract(pipeline.source_ir)
    optimized_ir = _ir_contract(pipeline.optimized_ir)
    type_contract = tuple(pipeline.optimized_ir.type_contract())
    schema_contract = tuple(
        (binding, repr(input_schema), repr(output_schema))
        for binding, input_schema, output_schema in pipeline.optimized_ir.schema_contract()
    )
    strategy_contract = tuple(
        (choice.node, choice.strategy) for choice in pipeline.strategies
    )
    effect_contract = tuple(
        (summary.node, tuple(sorted(summary.effects)))
        for summary in pipeline.effects
    )
    capability_report = pipeline.runtime_capability
    capability_contract = getattr(capability_report, "as_dict", lambda: repr(capability_report))()
    execution_profile = repr(pipeline.execution_profile)

    backend_payload = None if module is None else {"schema": "slang-backend-ast-1", "ast": _encode_payload(module)}
    selected_execution_plan = _selected_execution_plan_contract(pipeline.selected_execution_plan)
    operation_contract = _operation_contract(module)
    parameter_materialization = _parameter_materialization_contract(operation_contract)
    parameter_abi_descriptors = _parameter_abi_descriptor_contract(parameter_materialization)
    payload = {
        "artifact_version": ARTIFACT_VERSION,
        "source_ir": source_ir,
        "optimized_ir": optimized_ir,
        "type_contract": [list(x) for x in type_contract],
        "schema_contract": [list(x) for x in schema_contract],
        "strategy_contract": [list(x) for x in strategy_contract],
        "effect_contract": [[name, list(effects)] for name, effects in effect_contract],
        "capability_contract": capability_contract,
        "execution_profile": execution_profile,
        "backend_payload": backend_payload,
        "selected_execution_plan": selected_execution_plan,
        "operation_contract": [[binding, kind, params] for binding, kind, params in operation_contract],
        "parameter_materialization": [list(x) for x in parameter_materialization],
        "parameter_abi_descriptors": [list(x) for x in parameter_abi_descriptors],
    }
    fingerprint = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return CompilerArtifact(
        artifact_version=ARTIFACT_VERSION,
        source_ir=source_ir,
        optimized_ir=optimized_ir,
        type_contract=type_contract,
        schema_contract=schema_contract,
        strategy_contract=strategy_contract,
        effect_contract=effect_contract,
        capability_contract=capability_contract,
        execution_profile=execution_profile,
        fingerprint=fingerprint,
        backend_payload=backend_payload,
        selected_execution_plan=selected_execution_plan,
        operation_contract=operation_contract,
        parameter_materialization=parameter_materialization,
        parameter_abi_descriptors=parameter_abi_descriptors,
    )
