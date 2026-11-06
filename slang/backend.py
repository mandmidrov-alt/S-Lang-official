"""Backend capability model for S-Lang 0.92.

Semantic strategy selection is backend-independent.  This module describes
which selected strategies a concrete backend can actually lower, so planning
and backend capability remain separate and explicit.
"""
from __future__ import annotations
from dataclasses import dataclass
import shutil

from .compiler_pipeline import CompilerPipeline, compile_semantic_pipeline, compiler_artifact
from .compiler_artifact import CompilerArtifact
from .execution_contract import ExecutionContract, build_execution_contract


@dataclass(frozen=True)
class BackendCapabilities:
    name: str
    toolchain_ready: bool
    supported_domains: tuple[str, ...]
    supported_strategies: tuple[str, ...]
    supported_types: tuple[str, ...]
    supported_operations: tuple[str, ...]
    memory_models: tuple[str, ...]
    fusion_strategies: tuple[str, ...]
    runtime_features: tuple[str, ...]
    missing_tools: tuple[str, ...]
    supported_effects: tuple[str, ...] = ("pure",)
    supported_orderings: tuple[str, ...] = ("source-order",)
    supported_parallelism: tuple[str, ...] = ("sequential",)
    supported_materialization: tuple[str, ...] = ("backend-defined",)
    supported_execution_modes: tuple[str, ...] = ("materialized", "streaming")
    resource_preferences: tuple[tuple[str, float], ...] = ()

    def supports(self, strategy: str) -> bool:
        return strategy in self.supported_strategies

    def supports_fusion(self, strategy: str) -> bool:
        return strategy in self.fusion_strategies

    def supports_operation(self, operation: str) -> bool:
        return operation in self.supported_operations

    def supports_type(self, type_name: str) -> bool:
        if type_name in self.supported_types:
            return True
        # Structured types are resolved by semantic analysis. Backends only
        # need to advertise support for the container family, not rediscover
        # the record schema from AST nodes.
        if type_name.startswith("Record<"):
            return "Record" in self.supported_types or "List<Record>" in self.supported_types
        if type_name.startswith("List<Record<"):
            return "List<Record>" in self.supported_types
        if type_name.startswith("List<"):
            inner = type_name[5:-1]
            return "List" in self.supported_types or self.supports_type(inner)
        return False

    def supports_memory_model(self, model: str) -> bool:
        return model in self.memory_models

    def supports_execution_contract(self, contract: ExecutionContract) -> tuple[str, ...]:
        """Return deterministic reasons why this backend cannot honor a contract."""
        reasons: list[str] = []
        missing_ops = sorted(op for op in contract.operations if not self.supports_operation(op))
        if missing_ops:
            reasons.append("unsupported-operations=" + ",".join(missing_ops))
        missing_strategies = sorted(s for s in contract.strategies if not self.supports(s))
        if missing_strategies:
            reasons.append("unsupported-strategies=" + ",".join(missing_strategies))
        missing_memory = sorted(m for m in contract.memory_models if m != "abstract" and not self.supports_memory_model(m))
        if missing_memory:
            reasons.append("unsupported-memory-models=" + ",".join(missing_memory))
        missing_effects = sorted(e for e in contract.effects if e not in self.supported_effects)
        if missing_effects:
            reasons.append("unsupported-effects=" + ",".join(missing_effects))
        if contract.ordering not in self.supported_orderings:
            reasons.append("unsupported-ordering=" + contract.ordering)
        if contract.parallelism not in self.supported_parallelism:
            reasons.append("unsupported-parallelism=" + contract.parallelism)
        if (
            contract.materialization != "backend-defined"
            and contract.materialization not in self.supported_materialization
        ):
            reasons.append("unsupported-materialization=" + contract.materialization)
        return tuple(reasons)


@dataclass(frozen=True)
class BackendArtifact:
    backend: str
    source_nodes: int
    optimized_nodes: int
    strategy_count: int
    lowering: str
    executable: bool = False
    unsupported_strategies: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackendCandidate:
    backend: str
    compatible: bool
    toolchain_ready: bool
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackendSelection:
    selected: str | None
    candidates: tuple[BackendCandidate, ...]
    deterministic: bool = True


@dataclass(frozen=True)
class CompilationDecision:
    backend: str
    selection: BackendSelection
    pipeline: CompilerPipeline
    artifact: BackendArtifact
    lowering_contract: "BackendLoweringContract | None" = None
    execution_contract: ExecutionContract | None = None


@dataclass(frozen=True)
class CompilationResult:
    """Single compiler result shared by planning, artifact, lowering, and build stages."""
    decision: CompilationDecision
    lowered: "LoweredArtifact"
    artifact: "CompilerArtifact | None" = None


@dataclass(frozen=True)
class LoweredArtifact:
    """Concrete source emitted by the dispatcher for the selected backend."""
    backend: str
    strategy: str
    lowerer: str
    format: str
    text: str
    executable: bool = False


_NATIVE_STRATEGIES = (
    "generic", "scan-filter", "sequential-map", "sequential-aggregate",
    "sequential-reduce", "sequence-engine", "fused-filter-map-reduce",
    "fused-filter-map-aggregate", "stable-sort", "physics-domain",
)

_MLIR_STRATEGIES = (
    "generic", "scan-filter", "sequential-map", "sequential-aggregate",
    "sequential-reduce", "sequence-engine", "fused-filter-map-reduce",
    "fused-filter-map-aggregate", "parallel-filter", "parallel-map",
    "stable-sort", "parallel-stable-sort", "collection-filter",
    "collection-map", "collection-sort", "collection-aggregate",
    "collection-reduce", "sequence-engine", "goal-selection",
    "graph-search", "constraint-solver", "physics-backend",
)


def native_capabilities() -> BackendCapabilities:
    return BackendCapabilities(
        name="native-llvm",
        toolchain_ready=shutil.which("clang") is not None,
        supported_domains=("data.numeric", "physics.gravity"),
        supported_strategies=_NATIVE_STRATEGIES,
        supported_types=("Number", "Boolean", "Text", "List<Number>", "List<Row>", "Record", "List<Record>", "Quantity"),
        supported_operations=("filter", "map", "sort", "aggregate", "reduce", "sequence", "show", "physics.gravity", "exists", "file_size", "is_file", "is_directory", "write", "read", "read_lines", "list_directory", "make_directory", "remove_directory"),
        memory_models=("linear-buffer", "scalar-accumulator"),
        fusion_strategies=("fused-filter-map-reduce", "fused-filter-map-aggregate"),
        runtime_features=("slang_reduce_f64", "native-array-buffer", "slang-sequence-f64", "slang-file-io"),
        missing_tools=tuple(name for name in ("clang",) if shutil.which(name) is None),
        supported_effects=("pure", "io"),
        supported_orderings=("source-order",),
        supported_parallelism=("sequential",),
        supported_materialization=("streaming-when-fused", "backend-defined"),
        supported_execution_modes=("materialized", "streaming"),
        resource_preferences=(("memory", 2.0), ("materialization", 1.0), ("parallelism", 0.5), ("ordering", 0.25)),
    )


def mlir_toolchain_status() -> BackendCapabilities:
    required = ("mlir-opt", "mlir-translate", "clang")
    missing = tuple(name for name in required if shutil.which(name) is None)
    return BackendCapabilities(
        name="mlir-llvm",
        toolchain_ready=not missing,
        supported_domains=("physics.gravity",),
        supported_strategies=_MLIR_STRATEGIES,
        supported_types=("Number", "Boolean", "List<Number>", "List<Row>", "Record", "List<Record>", "Quantity"),
        supported_operations=("physics.gravity", "filter", "map", "sort", "aggregate", "reduce", "sequence", "choose", "find_path", "satisfy"),
        memory_models=("memref", "scalar-accumulator"),
        fusion_strategies=("fused-filter-map-reduce", "fused-filter-map-aggregate"),
        runtime_features=("mlir-arith", "mlir-scf", "mlir-func"),
        missing_tools=missing,
        supported_effects=("pure",),
        supported_orderings=("source-order", "dependency-ordered"),
        supported_parallelism=("sequential", "parallel-where-independent"),
        supported_materialization=("streaming-when-fused", "backend-defined"),
        supported_execution_modes=("materialized", "streaming", "parallel"),
        resource_preferences=(("parallelism", 2.0), ("memory", 1.0), ("materialization", 0.5), ("ordering", 0.5)),
    )


def capabilities_for(backend: str) -> BackendCapabilities:
    if backend == "native":
        return native_capabilities()
    if backend == "mlir":
        return mlir_toolchain_status()
    raise ValueError(f"unsupported backend '{backend}'")


def unsupported_strategies(pipeline: CompilerPipeline, capabilities: BackendCapabilities) -> tuple[str, ...]:
    missing = sorted({choice.strategy for choice in pipeline.strategies if not capabilities.supports(choice.strategy)})
    return tuple(missing)


def validate_backend_capabilities(pipeline: CompilerPipeline, capabilities: BackendCapabilities) -> None:
    missing = unsupported_strategies(pipeline, capabilities)
    if missing:
        raise ValueError(
            f"backend '{capabilities.name}' does not implement selected strategy(s): "
            + ", ".join(missing)
        )


def validate_execution_contract(contract: ExecutionContract, capabilities: BackendCapabilities) -> None:
    reasons = capabilities.supports_execution_contract(contract)
    if reasons:
        raise ValueError(
            f"backend '{capabilities.name}' cannot honor execution contract: "
            + "; ".join(reasons)
        )


def validate_backend_type_contract(pipeline: CompilerPipeline, capabilities: BackendCapabilities) -> None:
    """Validate the resolved semantic types without re-analyzing the AST.

    ExecutionIR is the sole source of truth here. Backend lowering consumes
    these resolved contracts and only checks whether its capability model can
    represent them.
    """
    required = sorted({
        t for node in pipeline.optimized_ir.nodes
        for t in (node.input_type, node.output_type)
        if t is not None
    })
    missing = [t for t in required if not capabilities.supports_type(t)]
    if missing:
        raise ValueError(
            f"backend '{capabilities.name}' does not support resolved type(s): "
            + ", ".join(missing)
        )


def validate_execution_regions(pipeline: CompilerPipeline, capabilities: BackendCapabilities) -> None:
    """Reject execution-region modes that the backend cannot lower explicitly."""
    modes = sorted({region.mode for region in pipeline.selected_execution_plan.execution_regions})
    missing = [mode for mode in modes if mode not in capabilities.supported_execution_modes]
    if missing:
        raise ValueError(
            f"backend '{capabilities.name}' does not support execution mode(s): "
            + ", ".join(missing)
        )


def _required_operations(pipeline: CompilerPipeline) -> tuple[str, ...]:
    mapping = {
        "filter": "filter",
        "map": "map",
        "sort": "sort",
        "aggregate": "aggregate",
        "reduce": "reduce",
        "sequence": "sequence",
        "goal:select": "choose",
        "goal:path": "find_path",
        "goal:satisfy": "satisfy", "goal:transition": "sequence",
        "physics.gravity": "physics.gravity",
        "effect:show": "show",
    }
    return tuple(sorted({mapping[n.kind] for n in pipeline.optimized_ir.nodes if n.kind in mapping}))


def _required_domains(module, pipeline: CompilerPipeline) -> tuple[str, ...]:
    domains: set[str] = set()
    ir_kinds = {n.kind for n in pipeline.optimized_ir.nodes}
    if "physics.gravity" in ir_kinds:
        domains.add("physics.gravity")
    if any(k in ir_kinds for k in ("filter", "map", "sort", "aggregate", "reduce", "sequence")):
        domains.add("data.numeric")
    if any(k.startswith("goal:") for k in ir_kinds):
        if "goal:select" in ir_kinds or "goal:path" in ir_kinds:
            domains.add("graph" if "goal:path" in ir_kinds else "data.numeric")
        if "goal:satisfy" in ir_kinds:
            domains.add("constraint")
    return tuple(sorted(domains))


def _backend_candidate(module, backend: str) -> BackendCandidate:
    caps = capabilities_for(backend)
    pipeline = compile_semantic_pipeline(module, caps.supported_strategies, caps.memory_models, caps.supported_orderings, caps.supported_parallelism, caps.supported_materialization, caps.resource_preferences)
    reasons: list[str] = []
    if not caps.toolchain_ready:
        reasons.append("toolchain-not-ready")
    execution_contract = build_execution_contract(pipeline)
    reasons.extend(caps.supports_execution_contract(execution_contract))
    missing_strategies = unsupported_strategies(pipeline, caps)
    required_domains = _required_domains(module, pipeline)
    missing_domains = tuple(sorted(d for d in required_domains if not caps.supported_domains or d not in caps.supported_domains))
    if missing_domains:
        reasons.append("unsupported-domains=" + ",".join(missing_domains))

    compatible = not reasons
    # Deterministic compiler policy: executable native LLVM is preferred when
    # both backends are otherwise compatible; MLIR is the fallback.
    preference = 0.0 if backend == "native" else 1.0
    readiness_penalty = 0.0 if caps.toolchain_ready else 1000.0
    score = preference + readiness_penalty + 10.0 * len(missing_strategies) + 20.0 * len(reasons) + 20.0 * len(missing_domains)
    return BackendCandidate(backend=caps.name, compatible=compatible, toolchain_ready=caps.toolchain_ready, score=score, reasons=tuple(reasons))


def select_backend(module, candidates: tuple[str, ...] = ("native", "mlir")) -> BackendSelection:
    """Select an executable backend from deterministic capability checks.

    This is deliberately separate from semantic algorithm selection: first the
    semantic plan is constrained by each backend, then incompatible backends
    are removed, and only then is the deterministic backend policy applied.
    """
    evaluated = tuple(_backend_candidate(module, name) for name in candidates)
    compatible = tuple(c for c in evaluated if c.compatible)
    selected = min(compatible, key=lambda c: (c.score, c.backend)).backend if compatible else None
    return BackendSelection(selected=selected, candidates=evaluated)



@dataclass(frozen=True)
class BackendLoweringContract:
    """Concrete lowering obligations exposed by a backend.

    Capabilities answer whether a backend may be selected.  The lowering
    contract answers how each selected strategy/operation is actually lowered,
    preventing a backend from advertising a strategy without a lowering path.
    """
    backend: str
    strategy_lowerers: tuple[tuple[str, str], ...]
    operation_lowerers: tuple[tuple[str, str], ...]
    executable_strategies: tuple[str, ...] = ()
    executable_operations: tuple[str, ...] = ()
    runtime_features: tuple[str, ...] = ()

    def lowerer_for_strategy(self, strategy: str) -> str | None:
        return dict(self.strategy_lowerers).get(strategy)

    def lowerer_for_operation(self, operation: str) -> str | None:
        return dict(self.operation_lowerers).get(operation)


def lowering_contract_for(backend: str) -> BackendLoweringContract:
    if backend == "native":
        return BackendLoweringContract(
            backend="native-llvm",
            strategy_lowerers=(
                ("generic", "native.reference"),
                ("scan-filter", "native.filter-loop"),
                ("sequential-map", "native.map-loop"),
                ("sequential-aggregate", "native.aggregate-loop"),
                ("sequential-reduce", "native.reduce-loop"),
                ("sequence-engine", "native.sequence-f64"),
                ("fused-filter-map-reduce", "native.fused-filter-map-reduce"),
                ("fused-filter-map-aggregate", "native.fused-filter-map-aggregate"),
                ("stable-sort", "native.stable-sort"),
                ("physics-domain", "native.physics-gravity"),
            ),
            operation_lowerers=(
                ("filter", "native.filter-loop"),
                ("map", "native.map-loop"),
                ("sort", "native.stable-sort"),
                ("aggregate", "native.aggregate-loop"),
                ("reduce", "native.reduce-loop"),
                ("sequence", "native.sequence-f64"),
                ("show", "native.printf"),
                ("physics.gravity", "native.physics-gravity"),
            ),
            executable_strategies=(
                "generic", "scan-filter", "sequential-map",
                "sequential-aggregate", "sequential-reduce", "sequence-engine",
                "fused-filter-map-reduce", "fused-filter-map-aggregate", "stable-sort",
                "physics-domain",
            ),
            executable_operations=("filter", "map", "sort", "aggregate", "reduce", "sequence", "show", "physics.gravity"),
            runtime_features=("slang_reduce_f64", "native-array-buffer", "slang-sequence-f64", "slang-file-io"),
        )
    if backend == "mlir":
        return BackendLoweringContract(
            backend="mlir-llvm",
            strategy_lowerers=(
                ("generic", "mlir.slang-generic"),
                ("scan-filter", "mlir.slang.filter"),
                ("sequential-map", "mlir.slang.map"),
                ("sequential-aggregate", "mlir.slang.aggregate"),
                ("sequential-reduce", "mlir.slang.reduce"),
                ("fused-filter-map-reduce", "mlir.slang.fused-filter-map-reduce"),
                ("fused-filter-map-aggregate", "mlir.slang.fused-filter-map-aggregate"),
                ("parallel-filter", "mlir.slang.parallel-filter"),
                ("parallel-map", "mlir.slang.parallel-map"),
                ("stable-sort", "mlir.slang.sort"),
                ("parallel-stable-sort", "mlir.slang.parallel-sort"),
                ("collection-filter", "mlir.slang.filter"),
                ("collection-map", "mlir.slang.map"),
                ("collection-sort", "mlir.slang.sort"),
                ("collection-aggregate", "mlir.slang.aggregate"),
                ("collection-reduce", "mlir.slang.reduce"),
                ("sequence-engine", "mlir.slang.sequence"),
                ("goal-selection", "mlir.slang.choose"),
                ("graph-search", "mlir.slang.find_path"),
                ("constraint-solver", "mlir.slang.satisfy"),
                ("physics-backend", "mlir.slang.simulate_gravity"),
            ),
            operation_lowerers=(
                ("filter", "mlir.slang.filter"), ("map", "mlir.slang.map"),
                ("sort", "mlir.slang.sort"), ("aggregate", "mlir.slang.aggregate"),
                ("reduce", "mlir.slang.reduce"), ("sequence", "mlir.slang.sequence"),
                ("choose", "mlir.slang.choose"), ("find_path", "mlir.slang.find_path"),
                ("satisfy", "mlir.slang.satisfy"), ("physics.gravity", "mlir.slang.simulate_gravity"),
            ),
            runtime_features=("mlir-arith", "mlir-scf", "mlir-func"),
        )
    raise ValueError(f"unsupported backend '{backend}'")


def validate_lowering_contract(pipeline: CompilerPipeline, contract: BackendLoweringContract) -> None:
    missing = sorted({choice.strategy for choice in pipeline.strategies if contract.lowerer_for_strategy(choice.strategy) is None})
    if missing:
        raise ValueError(
            f"backend '{contract.backend}' has no lowering contract for selected strategy(s): "
            + ", ".join(missing)
        )


def validate_contract_closure(
    execution_contract: ExecutionContract,
    lowering_contract: BackendLoweringContract,
    capabilities: BackendCapabilities,
) -> None:
    """Verify that execution obligations close all the way to concrete lowering.

    Capability validation answers whether a backend may honor the contract.
    Lowering validation answers whether every selected strategy has a lowering
    path.  This final closure check also requires every semantic operation to
    have a declared lowerer and every declared runtime feature to be advertised
    by the backend capabilities.
    """
    missing_operations = sorted(
        op for op in execution_contract.operations
        if lowering_contract.lowerer_for_operation(op) is None
    )
    if missing_operations:
        raise ValueError(
            f"backend '{lowering_contract.backend}' has no operation lowerer for: "
            + ", ".join(missing_operations)
        )

    missing_strategies = sorted(
        strategy for strategy in execution_contract.strategies
        if lowering_contract.lowerer_for_strategy(strategy) is None
    )
    if missing_strategies:
        raise ValueError(
            f"backend '{lowering_contract.backend}' has no strategy lowerer for: "
            + ", ".join(missing_strategies)
        )

    missing_runtime = sorted(
        feature for feature in lowering_contract.runtime_features
        if feature not in capabilities.runtime_features
    )
    if missing_runtime:
        raise ValueError(
            f"backend '{lowering_contract.backend}' does not advertise required runtime feature(s): "
            + ", ".join(missing_runtime)
        )


def lowering_contract_for_pipeline(pipeline: CompilerPipeline, backend: str) -> BackendLoweringContract:
    contract = lowering_contract_for(backend)
    validate_lowering_contract(pipeline, contract)
    return contract

def compile_selected_backend(module, backend: str = "auto") -> CompilationDecision:
    """Create the single compilation decision consumed by backend lowering.

    With ``auto``, backend selection is performed first. With an explicit
    backend, the same capability validation is applied to prevent the
    lowering stage from silently accepting an incompatible plan.
    """
    if backend == "auto":
        selection = select_backend(module)
        if selection.selected is None:
            details = "; ".join(
                f"{c.backend}: {', '.join(c.reasons) or 'incompatible'}"
                for c in selection.candidates
            )
            raise ValueError(f"no compatible executable backend ({details})")
        selected_name = "native" if selection.selected == "native-llvm" else "mlir"
    else:
        capabilities = capabilities_for(backend)
        candidate = _backend_candidate(module, backend)
        selection = BackendSelection(
            selected=capabilities.name if candidate.compatible else None,
            candidates=(candidate,),
        )
        if not candidate.compatible:
            raise ValueError(
                f"backend '{capabilities.name}' is not compatible: "
                + ("; ".join(candidate.reasons) if candidate.reasons else "unknown reason")
            )
        selected_name = backend

    pipeline, artifact = compile_for_backend(module, selected_name)
    contract = lowering_contract_for_pipeline(pipeline, selected_name)
    execution_contract = build_execution_contract(pipeline)
    capabilities = capabilities_for(selected_name)
    validate_execution_contract(execution_contract, capabilities)
    validate_backend_type_contract(pipeline, capabilities)
    validate_execution_regions(pipeline, capabilities)
    validate_contract_closure(execution_contract, contract, capabilities)
    return CompilationDecision(
        backend=artifact.backend,
        selection=selection,
        pipeline=pipeline,
        artifact=artifact,
        lowering_contract=contract,
        execution_contract=execution_contract,
    )




def compile_program(module, backend: str = "auto") -> CompilationResult:
    """Run the complete deterministic compiler pipeline through lowering.

    This is the canonical public compilation API: semantic planning, backend
    selection, capability validation, lowering-contract validation, and
    concrete lowering are executed exactly once and represented by one result.
    """
    decision = compile_selected_backend(module.ast if hasattr(module, "ast") else module, backend)
    lowered = lower_compilation_decision(module, decision)
    artifact = compiler_artifact(decision.pipeline, module=module.ast if hasattr(module, "ast") else module)
    return CompilationResult(decision=decision, lowered=lowered, artifact=artifact)


def lower_compiler_artifact(artifact: CompilerArtifact, backend: str = "native") -> LoweredArtifact:
    """Lower a serialized compiler artifact without requiring source text.

    The artifact carries a validated, JSON-safe semantic payload. The backend
    reconstructs only the S-Lang AST needed by the existing native/MLIR emitters
    and supplies the already-resolved compiler contracts, so semantic analysis
    is not rerun and the original source file is not consulted.
    """
    if not isinstance(artifact, CompilerArtifact):
        raise TypeError("lower_compiler_artifact expects CompilerArtifact")
    if artifact.artifact_version != "7":
        raise ValueError("unsupported compiler artifact version for backend lowering")
    module = artifact.backend_ast()
    if backend == "native":
        from .core import Program, Body, Circle, DataRow
        bodies = [Body(x.name, dict(x.fields)) for x in module.bodies]
        circles = [Circle(x.name, x.fields.get("radius")) for x in module.circles]
        sim = None
        if module.simulations:
            q = module.simulations[0]
            sim = (q.target, q.attractor, q.duration, q.step)
        show_pairs = []
        for op in module.shows:
            if hasattr(op.target, "name") and type(op.target).__name__ == "Name":
                show_pairs.append((op.target.name, "__value__"))
            elif type(op.target).__name__ == "Property" and hasattr(op.target.base, "name"):
                show_pairs.append((op.target.base.name, op.target.name))
        show_exprs = [op.target for op in module.shows]
        data_tables = {d.name: d.rows for d in module.datasets}
        people = [DataRow(r.get("name", ""), r.get("age", 0)) for rows in data_tables.values() for r in rows if "age" in r]
        program = Program(module.gravity, bodies, sim, show_pairs, show_exprs, people, None, circles, module, data_tables, {}, None)
        capabilities = capabilities_for("native")
        if not capabilities.toolchain_ready:
            raise ValueError("native LLVM backend toolchain is not ready")
        from .core import llvm_ir
        text = llvm_ir(program, type_contract=tuple(tuple(x) for x in artifact.type_contract),
                       schema_contract=tuple((x[0], x[1], x[2]) for x in artifact.schema_contract))
        strategy = artifact.strategy_contract[0][1] if artifact.strategy_contract else "generic"
        contract = lowering_contract_for("native")
        lowerer = contract.lowerer_for_strategy(strategy) or "native.reference"
        return LoweredArtifact(backend="native-llvm", strategy=strategy, lowerer=lowerer,
                               format="llvm-ir", text=text, executable=True)
    if backend == "mlir":
        from .mlir_backend import lower_compiler_artifact_to_mlir
        text = lower_compiler_artifact_to_mlir(artifact)
        strategy = artifact.strategy_contract[0][1] if artifact.strategy_contract else "generic"
        contract = lowering_contract_for("mlir")
        lowerer = contract.lowerer_for_strategy(strategy) or "mlir.slang-generic"
        return LoweredArtifact(backend="mlir-llvm", strategy=strategy, lowerer=lowerer,
                               format="mlir", text=text, executable=False)
    raise ValueError(f"unsupported artifact backend '{backend}'")


def lower_backend_artifact(artifact: CompilerArtifact, backend: str = "native") -> LoweredArtifact:
    """Unified persisted-artifact entry point for every concrete backend."""
    return lower_compiler_artifact(artifact, backend=backend)


def format_backend_selection(selection: BackendSelection) -> str:
    lines = ["backend.selection {"]
    for candidate in selection.candidates:
        lines.append(f"  candidate {candidate.backend} compatible={'yes' if candidate.compatible else 'no'} toolchain_ready={'yes' if candidate.toolchain_ready else 'no'} score={candidate.score:g}")
        lines.append("    reasons = " + ("; ".join(candidate.reasons) if candidate.reasons else "none"))
    lines.append("  selected = " + (selection.selected if selection.selected else "none"))
    lines.append("  deterministic = " + ("yes" if selection.deterministic else "no"))
    lines.append("  selection = capability-filtered-policy")
    lines.append("}")
    return "\n".join(lines)



def _selected_strategy_for_decision(module, decision: CompilationDecision) -> str:
    if not decision.pipeline.strategies:
        return "generic"
    choices = {choice.node: choice.strategy for choice in decision.pipeline.strategies}
    ast = module.ast
    terminal = None
    if ast.reduces:
        terminal = ast.reduces[0].result
    elif ast.aggregates:
        terminal = ast.aggregates[0].result
    elif ast.filters:
        terminal = ast.filters[-1].result
    elif ast.maps:
        terminal = ast.maps[-1].result
    if terminal is not None:
        return choices.get(terminal + "#1", choices.get(terminal, "generic"))
    # Non-collection programs currently use their first selected strategy.
    return decision.pipeline.strategies[0].strategy


def lower_compilation_decision(module, decision: CompilationDecision) -> LoweredArtifact:
    """Dispatch the already-selected compilation decision to a concrete emitter.

    This is the first point where semantic planning becomes backend-specific.
    No backend is allowed to silently substitute a different strategy: the
    selected strategy must have a declared lowering contract.
    """
    if decision.lowering_contract is None:
        raise ValueError("compilation decision has no lowering contract")
    validate_lowering_contract(decision.pipeline, decision.lowering_contract)
    if decision.execution_contract is None:
        raise ValueError("compilation decision has no execution contract")
    backend_name = "native" if decision.backend == "native-llvm" else "mlir"
    capabilities = capabilities_for(backend_name)
    validate_backend_type_contract(decision.pipeline, capabilities)
    validate_contract_closure(
        decision.execution_contract,
        decision.lowering_contract,
        capabilities,
    )

    from .core import llvm_ir, slang_mlir

    strategy = _selected_strategy_for_decision(module, decision)
    lowerer = decision.lowering_contract.lowerer_for_strategy(strategy)
    if lowerer is None:
        raise ValueError(f"no concrete lowerer for selected strategy '{strategy}'")

    if decision.backend == "native-llvm":
        text = llvm_ir(module, type_contract=decision.pipeline.optimized_ir.type_contract(), schema_contract=decision.pipeline.optimized_ir.schema_contract())
        return LoweredArtifact(
            backend=decision.backend, strategy=strategy, lowerer=lowerer,
            format="llvm-ir", text=text, executable=decision.artifact.executable,
        )
    if decision.backend == "mlir-llvm":
        from .mlir_backend import lower_execution_ir_to_mlir
        text = lower_execution_ir_to_mlir(module, pipeline=decision.pipeline)
        return LoweredArtifact(
            backend=decision.backend, strategy=strategy, lowerer=lowerer,
            format="mlir", text=text, executable=False,
        )
    raise ValueError(f"no lowering dispatcher for backend '{decision.backend}'")

def compile_for_backend(module, backend: str = "mlir") -> tuple[CompilerPipeline, BackendArtifact]:
    capabilities = capabilities_for(backend)
    pipeline = compile_semantic_pipeline(
        module, capabilities.supported_strategies, capabilities.memory_models,
        capabilities.supported_orderings, capabilities.supported_parallelism,
        capabilities.supported_materialization, capabilities.resource_preferences,
    )

    if backend == "mlir":
        domains = set()
        if module.bodies or module.simulations or module.gravity:
            domains.add("physics.gravity")
        if module.graphs or module.path_goals:
            domains.add("graph")
        if module.datasets or module.filters or module.maps or module.sorts or module.aggregates or module.reduces:
            domains.add("data")
        if module.satisfy_goals:
            domains.add("constraint")
        unsupported = sorted(domains - set(capabilities.supported_domains))
        if unsupported:
            raise ValueError(
                "MLIR backend does not yet lower these semantic domains: " + ", ".join(unsupported)
            )

    missing = unsupported_strategies(pipeline, capabilities)
    if missing:
        raise ValueError(
            f"backend '{capabilities.name}' cannot lower selected strategy(s): " + ", ".join(missing)
        )

    lowering = (
        "SelectedExecutionPlan regions -> native LLVM IR"
        if backend == "native"
        else "SelectedExecutionPlan regions -> slang dialect -> SCF/Arith/Func -> LLVM"
    )
    artifact = BackendArtifact(
        backend=capabilities.name,
        source_nodes=pipeline.source_nodes,
        optimized_nodes=pipeline.optimized_nodes,
        strategy_count=len(pipeline.strategies),
        lowering=lowering,
        executable=(backend == "native" and capabilities.toolchain_ready),
        unsupported_strategies=missing,
    )
    return pipeline, artifact


def format_backend_status(status: BackendCapabilities) -> str:
    lines = ["backend.status {", f"  backend = {status.name}"]
    lines.append("  toolchain_ready = " + ("yes" if status.toolchain_ready else "no"))
    lines.append("  supported_domains = " + ", ".join(status.supported_domains))
    lines.append("  supported_strategies = " + (", ".join(status.supported_strategies) if status.supported_strategies else "none"))
    lines.append("  supported_types = " + (", ".join(status.supported_types) if status.supported_types else "none"))
    lines.append("  supported_operations = " + (", ".join(status.supported_operations) if status.supported_operations else "none"))
    lines.append("  memory_models = " + (", ".join(status.memory_models) if status.memory_models else "none"))
    lines.append("  fusion_strategies = " + (", ".join(status.fusion_strategies) if status.fusion_strategies else "none"))
    lines.append("  runtime_features = " + (", ".join(status.runtime_features) if status.runtime_features else "none"))
    lines.append("  supported_effects = " + (", ".join(status.supported_effects) if status.supported_effects else "none"))
    lines.append("  supported_orderings = " + (", ".join(status.supported_orderings) if status.supported_orderings else "none"))
    lines.append("  supported_parallelism = " + (", ".join(status.supported_parallelism) if status.supported_parallelism else "none"))
    lines.append("  supported_materialization = " + (", ".join(status.supported_materialization) if status.supported_materialization else "none"))
    lines.append("  supported_execution_modes = " + (", ".join(status.supported_execution_modes) if status.supported_execution_modes else "none"))
    lines.append("  missing_tools = " + (", ".join(status.missing_tools) if status.missing_tools else "none"))
    lines.append("  runtime_execution = not-invoked")
    lines.append("}")
    return "\n".join(lines)


def format_compilation_decision(decision: CompilationDecision) -> str:
    lines = ["compilation.decision {"]
    lines.append(f"  backend = {decision.backend}")
    lines.append(f"  source_nodes = {decision.pipeline.source_nodes}")
    lines.append(f"  optimized_nodes = {decision.pipeline.optimized_nodes}")
    lines.append(f"  strategies = {len(decision.pipeline.strategies)}")
    lines.append("  selection = capability-filtered-policy")
    lines.append("  lowering = selected-backend")
    if decision.lowering_contract is not None:
        lines.append("  lowering_contract = present")
        lines.append("  contracted_strategies = " + ", ".join(s for s, _ in decision.lowering_contract.strategy_lowerers))
    else:
        lines.append("  lowering_contract = absent")
    lines.append("  executable = " + ("yes" if decision.artifact.executable else "not-yet-emitted"))
    lines.append("}")
    return "\n".join(lines)


def format_backend_artifact(artifact: BackendArtifact) -> str:
    return "\n".join([
        "backend.lowering {",
        f"  backend = {artifact.backend}",
        f"  source_nodes = {artifact.source_nodes}",
        f"  optimized_nodes = {artifact.optimized_nodes}",
        f"  strategy_count = {artifact.strategy_count}",
        f"  lowering = {artifact.lowering}",
        "  executable = " + ("yes" if artifact.executable else "not-yet-emitted"),
        "  unsupported_strategies = " + (", ".join(artifact.unsupported_strategies) if artifact.unsupported_strategies else "none"),
        "}",
    ])
