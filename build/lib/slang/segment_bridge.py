"""Explicit state handoff between plan-runtime and reference segments.

The bridge is deliberately runtime-neutral: it snapshots the mutable runtime
namespace at a segment boundary and restores the returned namespace after a
fallback segment.  This prevents a fallback implementation from receiving a
second, independently initialized program state.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import copy


@dataclass
class SegmentDataContract:
    """Minimal namespace contract crossing one execution-segment boundary."""
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    state_inputs: tuple[str, ...] = ()
    state_outputs: tuple[str, ...] = ()
    entity_inputs: tuple[str, ...] = ()
    entity_outputs: tuple[str, ...] = ()
    data_inputs: tuple[str, ...] = ()


@dataclass
class SegmentHandoff:
    segment_index: int
    mode: str
    bindings: dict[str, object] = field(default_factory=dict)
    collections: dict[str, object] = field(default_factory=dict)
    states: dict[str, object] = field(default_factory=dict)
    entities: dict[str, object] = field(default_factory=dict)
    data_result_name: str | None = None
    data_result: object = None
    contract: SegmentDataContract | None = None
    data_tables: dict[str, object] = field(default_factory=dict)


def capture(module, segment_index: int, mode: str, contract: SegmentDataContract | None = None) -> SegmentHandoff:
    """Capture a segment boundary; absent a contract, preserve legacy full snapshot behavior."""
    if contract is None:
        bindings = dict(getattr(module, "_bindings", {}) or {})
        collections = {k: list(v) if isinstance(v, list) else copy(v)
                      for k, v in (getattr(module, "_collections", {}) or {}).items()}
        states = dict(getattr(module, "_states", {}) or {})
        entities = dict(getattr(module, "entities", {}) or {})
        data_tables = dict(getattr(module, "data_tables", {}) or {})
    else:
        bindings_ns = getattr(module, "_bindings", {}) or {}
        collections_ns = getattr(module, "_collections", {}) or {}
        states_ns = getattr(module, "_states", {}) or {}
        entities_ns = getattr(module, "entities", {}) or {}
        names = set(contract.inputs) | set(contract.outputs)
        bindings = {k: bindings_ns[k] for k in names if k in bindings_ns}
        collections = {k: list(collections_ns[k]) if isinstance(collections_ns[k], list) else copy(collections_ns[k])
                      for k in names if k in collections_ns}
        states = {k: states_ns[k] for k in set(contract.state_inputs) | set(contract.state_outputs) if k in states_ns}
        entities = {k: entities_ns[k] for k in set(contract.entity_inputs) | set(contract.entity_outputs) if k in entities_ns}
        data_ns = getattr(module, "data_tables", {}) or {}
        data_tables = {k: data_ns[k] for k in contract.data_inputs if k in data_ns}
    return SegmentHandoff(
        segment_index=segment_index, mode=mode, bindings=bindings, collections=collections,
        states=states, entities=entities, data_result_name=getattr(module, "_data_result_name", None),
        data_result=getattr(module, "_data_result", None), contract=contract, data_tables=data_tables,
    )


def _transitive_flow_requirements(segments, dependency_edges, nodes):
    """Derive values/state that must survive every segment on a dependency path."""
    segment_of = {node: segment.index for segment in segments for node in segment.nodes}
    value_inputs = {segment.index: set() for segment in segments}
    value_outputs = {segment.index: set() for segment in segments}
    state_inputs = {segment.index: set() for segment in segments}
    state_outputs = {segment.index: set() for segment in segments}
    for edge in dependency_edges or ():
        before = segment_of.get(edge.before); after = segment_of.get(edge.after)
        if before is None or after is None or before >= after:
            continue
        producer = nodes.get(edge.before)
        value = producer.result if producer and producer.result else edge.before.rsplit("#", 1)[0]
        states = set(producer.memory_writes) if producer and producer.memory_writes else set()
        for index in range(before, after + 1):
            if index != before:
                value_inputs[index].add(value)
                state_inputs[index].update(states)
            if index != after:
                value_outputs[index].add(value)
                state_outputs[index].update(states)
    return value_inputs, value_outputs, state_inputs, state_outputs


def build_segment_data_contracts(segments, dependency_edges, ir, external_names=()) -> dict[int, SegmentDataContract]:
    """Build deterministic data/state/entity transfer contracts from the IR graph."""
    nodes = ir.by_binding()
    segment_of = {node: segment.index for segment in segments for node in segment.nodes}
    trans_inputs, trans_outputs, trans_state_inputs, trans_state_outputs = _transitive_flow_requirements(segments, dependency_edges, nodes)
    preds = {node: set() for node in nodes}
    succs = {node: set() for node in nodes}
    for edge in dependency_edges or ():
        if edge.before in nodes and edge.after in nodes:
            preds.setdefault(edge.after, set()).add(edge.before)
            succs.setdefault(edge.before, set()).add(edge.after)

    contracts = {}
    for segment in segments:
        inside = set(segment.nodes)
        inputs, outputs = set(), set()
        state_inputs, state_outputs = set(), set()
        entity_inputs, entity_outputs = set(), set()
        data_inputs = set()
        for binding in segment.nodes:
            node = nodes.get(binding)
            if node is None:
                continue
            for dep in preds.get(binding, ()):
                if dep not in inside:
                    producer = nodes.get(dep)
                    value_name = producer.result if producer and producer.result else dep
                    if value_name and not value_name.startswith('@state:'):
                        inputs.add(value_name)
                    if producer and producer.memory_writes:
                        state_inputs.update(producer.memory_writes)
            for external in node.external_sources:
                if external and not external.startswith('@'):
                    inputs.add(external)
            # Literal data tables are immutable external roots rather than IR
            # producer nodes; only tables explicitly requested by a segment
            # are admitted to its boundary.
            inputs.update(name for name in external_names if name in node.external_sources)
            if node.memory_reads:
                state_inputs.update(node.memory_reads)
            for region in node.memory_regions:
                root = region.split("[", 1)[0].split(".", 1)[0]
                if root and root not in {n.result for n in nodes.values() if n.result}:
                    data_inputs.add(root)
            if node.kind == 'physics.gravity':
                entity_inputs.update(node.external_sources)
            for succ in succs.get(binding, ()):
                if succ not in inside:
                    value_name = node.result if node.result else binding
                    if value_name and not value_name.startswith('@state:'):
                        outputs.add(value_name)
            if node.memory_writes:
                state_outputs.update(node.memory_writes)
            if node.kind == 'physics.gravity':
                entity_outputs.update(node.external_sources)
        # Preserve values/state across intermediate segments on transitive paths.
        inputs.update(trans_inputs.get(segment.index, ()))
        outputs.update(trans_outputs.get(segment.index, ()))
        state_inputs.update(trans_state_inputs.get(segment.index, ()))
        state_outputs.update(trans_state_outputs.get(segment.index, ()))
        # The terminal segment must expose the final semantic result.
        if segment is segments[-1]:
            for binding in segment.nodes:
                node = nodes.get(binding)
                if node and node.result and not node.result.startswith('@'):
                    outputs.add(node.result)
        contracts[segment.index] = SegmentDataContract(
            inputs=tuple(sorted(inputs)), outputs=tuple(sorted(outputs)),
            state_inputs=tuple(sorted(state_inputs)), state_outputs=tuple(sorted(state_outputs)),
            entity_inputs=tuple(sorted(entity_inputs)), entity_outputs=tuple(sorted(entity_outputs)),
            data_inputs=tuple(sorted(data_inputs)),
        )
    return contracts


def restore(module, handoff: SegmentHandoff) -> None:
    """Restore values produced by a segment into the shared module namespace."""
    module._bindings = dict(handoff.bindings)
    module._collections = dict(handoff.collections)
    module._states = dict(handoff.states)
    module.entities = dict(handoff.entities)
    module._data_result_name = handoff.data_result_name
    module._data_result = handoff.data_result


def _state_snapshot(states, names):
    """Snapshot only contract-visible state, preserving simple value semantics."""
    return {name: copy(states[name]) for name in names if name in states}


def validate_runtime_state_boundary(module, contract, before, *, segment_index):
    """Validate the concrete state crossing a segment boundary.

    Inputs must exist before execution; only declared outputs may be created or
    changed across the boundary.  This turns the static state contract into a
    runtime invariant without exposing unrelated state to fallback adapters.
    """
    if contract is None:
        return True
    states = getattr(module, "_states", {}) or {}
    for name in contract.state_inputs:
        if name not in states:
            raise RuntimeError(
                f"segment {segment_index} missing runtime state input: {name!r}"
            )
    output_names = set(contract.state_outputs)
    after = states
    for name in output_names:
        if name not in after:
            raise RuntimeError(
                f"segment {segment_index} missing declared runtime state output: {name!r}"
            )
    # A segment is allowed to change only state declared as an output.  Compare
    # the states visible at entry so accidental writes become deterministic
    # diagnostics rather than silently leaking across the bridge.
    for name, old_value in before.items():
        if name in output_names or name not in after:
            continue
        new_value = after[name]
        try:
            changed = new_value != old_value
        except Exception:
            changed = new_value is not old_value
        if changed:
            raise RuntimeError(
                f"segment {segment_index} changed undeclared runtime state: {name!r}"
            )
    return True


def execute_reference_segment(module, segment, handoff: SegmentHandoff, executor=None):
    """Execute a fallback through a selective isolated boundary when contracted."""
    if executor is None:
        raise RuntimeError(
            "reference segment has no registered segment executor; "
            f"segment {segment.index} requires an explicit fallback adapter"
        )
    if handoff.contract is None:
        result = executor(module, segment, handoff)
        if result is not None and result is not module:
            raise TypeError("reference segment executor must mutate the shared module or return None")
        return module
    isolated = copy(module)
    isolated._bindings = dict(handoff.bindings)
    isolated._collections = {k: list(v) if isinstance(v, list) else copy(v) for k, v in handoff.collections.items()}
    isolated._states = dict(handoff.states)
    isolated.entities = dict(handoff.entities)
    isolated.data_tables = dict(handoff.data_tables)
    for name, value in isolated.data_tables.items():
        if name not in isolated._collections:
            isolated._collections[name] = list(value) if isinstance(value, list) else copy(value)
    isolated._data_result_name = handoff.data_result_name
    isolated._data_result = handoff.data_result
    result = executor(isolated, segment, handoff)
    if result is not None and result is not isolated:
        raise TypeError("reference segment executor must mutate the isolated module or return None")
    contract = handoff.contract
    for name in contract.outputs:
        if name in isolated._bindings:
            module._bindings[name] = isolated._bindings[name]
        if name in isolated._collections:
            module._collections[name] = isolated._collections[name]
    for name in contract.state_outputs:
        if name in isolated._states:
            module._states[name] = isolated._states[name]
    for name in contract.entity_outputs:
        if name in isolated.entities:
            module.entities[name] = isolated.entities[name]
    if contract.outputs:
        module._data_result_name = getattr(isolated, '_data_result_name', None)
        module._data_result = getattr(isolated, '_data_result', None)
    return module


def required_segment_kinds(segment, node_kinds):
    """Return unique semantic kinds required by a reference segment."""
    return tuple(dict.fromkeys(node_kinds.get(node, "unknown") for node in segment.nodes))

def validate_reference_adapter(segment, node_kinds, executor_registry):
    """Preflight a fallback segment before any state mutation occurs."""
    required = required_segment_kinds(segment, node_kinds)
    missing = tuple(kind for kind in required if kind not in executor_registry)
    if missing:
        raise RuntimeError(
            "reference segment adapter preflight failed: "
            f"segment {segment.index} requires {missing!r}"
        )
    return required


def validate_segment_contracts(segments, contracts, dependency_edges, ir=None):
    """Validate static boundary contracts for completeness and minimality.

    A contract is valid only when every cross-segment value/state dependency is
    represented and no unrelated binding, state, entity, or data root is
    exported/imported.  When ``ir`` is available the validator also derives
    the allowed boundary sets directly from the selected execution graph.
    """
    if set(contracts) != {segment.index for segment in segments}:
        raise ValueError("segment data contracts do not cover all execution segments")

    segment_of = {node: segment.index for segment in segments for node in segment.nodes}
    nodes = ir.by_binding() if ir is not None else {}
    predecessors = {node: set() for node in nodes}
    successors = {node: set() for node in nodes}
    for edge in dependency_edges or ():
        if edge.before in nodes and edge.after in nodes:
            predecessors.setdefault(edge.after, set()).add(edge.before)
            successors.setdefault(edge.before, set()).add(edge.after)

    for edge in dependency_edges or ():
        before = segment_of.get(edge.before)
        after = segment_of.get(edge.after)
        if before is None or after is None or before == after:
            continue
        contract = contracts[after]
        producer = nodes.get(edge.before)
        producer_name = producer.result if producer and producer.result else edge.before.rsplit("#", 1)[0]
        if edge.kind == "state" or (producer and producer.memory_writes):
            if not any(name in contract.state_inputs for name in producer.memory_writes if producer):
                raise ValueError(
                    f"segment contract missing state dependency input: {edge.before} -> {edge.after}"
                )
        elif producer_name not in contract.inputs and edge.before not in contract.inputs:
            raise ValueError(
                f"segment contract missing dependency input: {edge.before} -> {edge.after}"
            )

    if ir is None:
        return True

    trans_inputs, trans_outputs, trans_state_inputs, trans_state_outputs = _transitive_flow_requirements(
        segments, dependency_edges, nodes
    )

    for segment in segments:
        inside = set(segment.nodes)
        contract = contracts[segment.index]
        required_inputs = set()
        allowed_outputs = set()
        required_state_inputs = set()
        allowed_state_outputs = set()
        required_entity_inputs = set()
        allowed_entity_outputs = set()
        required_data_inputs = set()

        for binding in segment.nodes:
            node = nodes.get(binding)
            if node is None:
                continue
            for dep in predecessors.get(binding, ()):
                if dep in inside:
                    continue
                producer = nodes.get(dep)
                if producer and producer.memory_writes:
                    required_state_inputs.update(producer.memory_writes)
                else:
                    required_inputs.add(producer.result if producer and producer.result else dep.rsplit("#", 1)[0])
            produced_names = {n.result for n in nodes.values() if n.result}
            for external in node.external_sources:
                if external and external not in produced_names:
                    required_inputs.add(external)
            if node.memory_reads:
                required_state_inputs.update(node.memory_reads)
            for region in node.memory_regions:
                root = region.split("[", 1)[0].split(".", 1)[0]
                if root and root not in {n.result for n in nodes.values() if n.result}:
                    required_data_inputs.add(root)
            if node.kind == "physics.gravity":
                required_entity_inputs.update(node.external_sources)
            for succ in successors.get(binding, ()):
                if succ in inside:
                    continue
                value = node.result if node.result else binding.rsplit("#", 1)[0]
                if value and not value.startswith("@state:"):
                    allowed_outputs.add(value)
            if node.memory_writes:
                cross_state = any(succ not in inside for succ in successors.get(binding, ()))
                if cross_state or segment is segments[-1]:
                    allowed_state_outputs.update(node.memory_writes)
            if node.kind == "physics.gravity":
                if any(succ not in inside for succ in successors.get(binding, ())):
                    allowed_entity_outputs.update(node.external_sources)
                elif segment is segments[-1]:
                    allowed_entity_outputs.update(node.external_sources)

        required_inputs.update(trans_inputs.get(segment.index, ()))
        allowed_outputs.update(trans_outputs.get(segment.index, ()))
        required_state_inputs.update(trans_state_inputs.get(segment.index, ()))
        allowed_state_outputs.update(trans_state_outputs.get(segment.index, ()))

        if segment is segments[-1]:
            for binding in segment.nodes:
                node = nodes.get(binding)
                if node and node.result and not node.result.startswith("@"):
                    allowed_outputs.add(node.result)

        actual = {
            "inputs": set(contract.inputs),
            "outputs": set(contract.outputs),
            "state_inputs": set(contract.state_inputs),
            "state_outputs": set(contract.state_outputs),
            "entity_inputs": set(contract.entity_inputs),
            "entity_outputs": set(contract.entity_outputs),
            "data_inputs": set(contract.data_inputs),
        }
        expected = {
            "inputs": required_inputs,
            "outputs": allowed_outputs,
            "state_inputs": required_state_inputs,
            "state_outputs": allowed_state_outputs,
            "entity_inputs": required_entity_inputs,
            "entity_outputs": allowed_entity_outputs,
            "data_inputs": required_data_inputs,
        }
        for field in expected:
            missing = expected[field] - actual[field]
            extra = actual[field] - expected[field]
            if missing:
                raise ValueError(
                    f"segment {segment.index} contract incomplete for {field}: {sorted(missing)!r}"
                )
            if extra:
                raise ValueError(
                    f"segment {segment.index} contract contains unnecessary {field}: {sorted(extra)!r}"
                )
    return True


def validate_segment_dependencies(segments, dependency_edges):
    """Validate that segment order respects every selected dependency edge."""
    segment_of = {node: segment.index for segment in segments for node in segment.nodes}
    for edge in dependency_edges:
        before = segment_of.get(edge.before)
        after = segment_of.get(edge.after)
        if before is None or after is None:
            continue
        if before > after:
            raise ValueError(
                f"segment dependency order violation: {edge.before} -> {edge.after}"
            )
    return True
