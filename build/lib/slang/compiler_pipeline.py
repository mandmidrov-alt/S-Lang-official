"""Unified semantic compiler pipeline for S-Lang 0.75.

This module connects the semantic compiler stages that were previously exposed
as separate analyses. It is deliberately analysis/planning only: no runtime
backend is invoked here.
"""
from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR, build_execution_ir
from .pipeline_ir import PipelineIR, build_pipeline_ir
from .execution_optimizer import ExecutionOptimizationReport, optimize_execution_ir
from .dependency_graph import DependencyGraph, build_dependency_graph
from .dependency_analysis import DependencyAnalysis, analyze_dependency_graph
from .execution_plan import ExecutionPlan, build_execution_plan
from .strategy_selection import StrategyChoice, build_strategy_choices
from .execution_profile import ExecutionProfile
from .selected_execution_plan import SelectedExecutionPlan, build_selected_execution_plan
from .effect_analysis import EffectSummary, analyze_effects, validate_strategy_effects
from .function_effects import FunctionEffectSummary, analyze_function_effects
from .higher_order_effects import HigherOrderEffectSummary, analyze_higher_order_effects
from .runtime_capability import RuntimeCapabilityReport, audit_runtime_capability
from .global_plan_optimizer import GlobalPlanCost, optimize_strategy_choices
from .optimizer import optimize_program, enumerate_record_plan_options
from .compiler_artifact import CompilerArtifact, build_compiler_artifact
import copy
from types import SimpleNamespace


@dataclass(frozen=True)
class CompilerPipeline:
    """Complete semantic planning state for one S-Lang module."""
    source_ir: ExecutionIR
    optimized_ir: ExecutionIR
    optimization: ExecutionOptimizationReport
    dependency_graph: DependencyGraph
    dependency_analysis: DependencyAnalysis
    execution_plan: ExecutionPlan
    strategies: tuple[StrategyChoice, ...]
    selected_execution_plan: SelectedExecutionPlan
    execution_explanation: object
    effects: tuple[EffectSummary, ...]
    function_effects: tuple[FunctionEffectSummary, ...]
    higher_order_effects: tuple[HigherOrderEffectSummary, ...]
    runtime_capability: RuntimeCapabilityReport | None = None
    global_plan_cost: GlobalPlanCost | None = None
    execution_profile: ExecutionProfile = ExecutionProfile.reference()
    pipeline_ir: PipelineIR | None = None

    @property
    def source_nodes(self) -> int:
        return len(self.source_ir.nodes)

    @property
    def optimized_nodes(self) -> int:
        return len(self.optimized_ir.nodes)



def _build_pipeline_ir_for_module(ir, module):
    terminals = []
    if getattr(module, "aggregates", ()):
        terminals.append(module.aggregates[0].result)
    elif getattr(module, "reduces", ()):
        terminals.append(module.reduces[0].result)
    elif getattr(module, "sorts", ()):
        terminals.append(module.sorts[0].result)
    if not terminals:
        for op in getattr(module, "maps", ()): terminals.append(op.result)
        for op in getattr(module, "filters", ()): terminals.append(op.result)
    if not terminals:
        return None
    try:
        return build_pipeline_ir(ir, terminals[-1])
    except ValueError:
        return None

def compile_semantic_pipeline(module, backend_supported_strategies: tuple[str, ...] | None = None, backend_memory_models: tuple[str, ...] | None = None, backend_orderings: tuple[str, ...] | None = None, backend_parallelism: tuple[str, ...] | None = None, backend_materialization: tuple[str, ...] | None = None, backend_resource_preferences: tuple[tuple[str, float], ...] | None = None, execution_profile: ExecutionProfile | None = None) -> CompilerPipeline:
    """Run the deterministic semantic compiler pipeline in one pass.

    Order is intentional:
      AST -> ExecutionIR -> static optimization -> dependency graph ->
      dependency analysis -> execution plan -> algorithm selection.

    Every later stage consumes the output of the preceding stage. This makes
    the pipeline the canonical planning path for future native backends.
    """
    profile = execution_profile or ExecutionProfile.reference()
    profile_preferences = profile.preferences()
    merged = dict(profile_preferences)
    merged.update(dict(backend_resource_preferences or ()))
    merged_preferences = tuple(sorted(merged.items()))
    effective_parallelism = backend_parallelism
    if not profile.allow_parallelism or profile.cpu_cores <= 1:
        # The execution profile is a hard resource constraint. Parallel
        # execution is only eligible when explicitly allowed and more than one
        # CPU core is available; backend capabilities still determine legality.
        effective_parallelism = tuple(p for p in (backend_parallelism or ("sequential",)) if p == "sequential") or ("sequential",)
    source_ir = build_execution_ir(module)
    optimized_ir, optimization = optimize_execution_ir(source_ir)
    graph = build_dependency_graph(optimized_ir)
    analysis = analyze_dependency_graph(optimized_ir, graph)
    plan = build_execution_plan(optimized_ir, analysis, graph, backend_supported_strategies)
    strategies = build_strategy_choices(plan, optimized_ir, backend_supported_strategies, backend_memory_models, backend_orderings, effective_parallelism, backend_materialization, merged_preferences)
    # Record transformation planning is maintained at the semantic AST layer.
    # Analyze a private copy here so the canonical ExecutionIR remains owned by
    # the execution optimizer, while the whole-graph objective still sees the
    # Record fusion/materialization signal.
    record_probe = SimpleNamespace(ast=copy.deepcopy(module), shows=[], show_exprs=[])
    record_option_probe = SimpleNamespace(ast=copy.deepcopy(module), shows=[], show_exprs=[])
    record_plan_options = enumerate_record_plan_options(record_option_probe)
    optimize_program(record_probe)
    record_decisions = tuple(getattr(record_probe, "_record_fusion_decisions", ()) or ())
    record_plan = record_decisions[0] if record_decisions else None
    # The global optimizer now evaluates Record-plan alternatives in the same
    # search as ordinary strategy alternatives. The selected Record mode is
    # therefore part of the authoritative global planning result.
    strategies, global_plan_cost = optimize_strategy_choices(
        graph.edges, plan.fusion_groups, strategies, optimized_ir, record_plan, record_plan_options, module
    )
    effect_summaries = analyze_effects(optimized_ir)
    function_effect_summaries = analyze_function_effects(module)
    higher_order_function_effects = {s.function: s.effects for s in function_effect_summaries}
    for summary in function_effect_summaries:
        if summary.returned_function_effects:
            higher_order_function_effects[summary.function + ".__return__"] = summary.returned_function_effects
    higher_order_effect_summaries = analyze_higher_order_effects(module, higher_order_function_effects)
    effect_errors = validate_strategy_effects(optimized_ir, strategies)
    if effect_errors:
        raise ValueError("effect safety violation: " + "; ".join(effect_errors))
    selected_plan = build_selected_execution_plan(
        plan, strategies, profile,
        node_kinds={n.binding: n.kind for n in optimized_ir.nodes},
        dependency_edges=graph.edges,
        ir=optimized_ir,
        external_names=tuple(getattr(module, "data_tables", {}) or {}),
        record_plan=getattr(global_plan_cost, "record_plan", None),
    )
    pipeline = CompilerPipeline(
        source_ir=source_ir,
        optimized_ir=optimized_ir,
        optimization=optimization,
        dependency_graph=graph,
        dependency_analysis=analysis,
        execution_plan=plan,
        strategies=strategies,
        selected_execution_plan=selected_plan,
        execution_explanation=None,
        effects=effect_summaries,
        function_effects=function_effect_summaries,
        higher_order_effects=higher_order_effect_summaries,
        runtime_capability=None,
        global_plan_cost=global_plan_cost,
        execution_profile=profile,
        pipeline_ir=_build_pipeline_ir_for_module(optimized_ir, module),
    )
    runtime_capability = audit_runtime_capability(pipeline)
    pipeline = CompilerPipeline(
        source_ir=pipeline.source_ir, optimized_ir=pipeline.optimized_ir,
        optimization=pipeline.optimization, dependency_graph=pipeline.dependency_graph,
        dependency_analysis=pipeline.dependency_analysis, execution_plan=pipeline.execution_plan,
        strategies=pipeline.strategies, selected_execution_plan=pipeline.selected_execution_plan,
        execution_explanation=None, effects=pipeline.effects, function_effects=pipeline.function_effects,
        higher_order_effects=pipeline.higher_order_effects, runtime_capability=runtime_capability,
        global_plan_cost=pipeline.global_plan_cost, execution_profile=pipeline.execution_profile, pipeline_ir=pipeline.pipeline_ir,
    )
    from .explainability import explain_compiler_pipeline
    return CompilerPipeline(
        source_ir=pipeline.source_ir, optimized_ir=pipeline.optimized_ir,
        optimization=pipeline.optimization, dependency_graph=pipeline.dependency_graph,
        dependency_analysis=pipeline.dependency_analysis, execution_plan=pipeline.execution_plan,
        strategies=pipeline.strategies, selected_execution_plan=pipeline.selected_execution_plan,
        execution_explanation=explain_compiler_pipeline(pipeline), effects=pipeline.effects,
        function_effects=pipeline.function_effects, higher_order_effects=pipeline.higher_order_effects,
        runtime_capability=runtime_capability, global_plan_cost=pipeline.global_plan_cost, execution_profile=pipeline.execution_profile, pipeline_ir=pipeline.pipeline_ir,
    )


def compiler_artifact(result: CompilerPipeline, module=None) -> CompilerArtifact:
    """Materialize the stable backend-neutral artifact for a compiled pipeline.

    ``module`` is optional for compatibility. The canonical compiler entry
    point supplies it so a serialized artifact can later be lowered without
    reopening the original source file.
    """
    return build_compiler_artifact(result, module=module)


def format_compiler_pipeline(result: CompilerPipeline) -> str:
    lines = ["compiler.pipeline {"]
    lines.append("  stage 0: semantic-ir")
    lines.append(f"    nodes = {result.source_nodes}")
    lines.append("  stage 1: execution-ir-optimization")
    lines.append(f"    nodes = {result.optimized_nodes}")
    lines.append(f"    transformations = {result.optimization.total}")
    lines.append("  stage 2: dependency-graph")
    lines.append(f"    edges = {len(result.dependency_graph.edges)}")
    lines.append("  stage 3: dependency-analysis")
    lines.append(f"    levels = {len(result.dependency_analysis.levels)}")
    lines.append(f"    critical_path_length = {result.dependency_analysis.critical_path_length}")
    lines.append("  stage 4: execution-plan")
    lines.append(f"    steps = {len(result.execution_plan.steps)}")
    lines.append(f"    parallel_groups = {len(result.execution_plan.selected_parallel_groups)}")
    lines.append("  stage 5: algorithm-selection")
    lines.append(f"    choices = {len(result.strategies)}")
    lines.append(f"    selected_plan_operations = {result.selected_execution_plan.operation_count}")
    lines.append(f"  execution_profile = cpu:{result.execution_profile.cpu_cores} parallel:{'yes' if result.execution_profile.allow_parallelism else 'no'}")
    lines.append(f"  effects = {len(result.effects)} analyzed")
    lines.append(f"  function_effect_contracts = {len(result.function_effects)} analyzed")
    lines.append(f"  higher_order_effects = {len(result.higher_order_effects)} analyzed")
    capability = result.runtime_capability
    lines.append(f"  runtime_capability = {'plan-runtime' if capability and capability.unified_supported else 'reference-fallback'}")
    lines.append(f"  runtime_supported_nodes = {capability.supported_nodes}/{capability.total_nodes}" if capability else "  runtime_supported_nodes = not-audited")
    if result.global_plan_cost is not None:
        g = result.global_plan_cost
        lines.append(f"  global_plan_cost = {g.total_cost:g} (local={g.local_cost:g}, boundaries={g.boundary_cost:g}, chain={g.chain_cost:g}, cardinality_weighted={g.cardinality_weighted_cost:g}, selectivity_weighted={g.selectivity_weighted_cost:g}, record_fusion={g.record_fusion_cost:g}, peak_cardinality={g.estimated_peak_cardinality if g.estimated_peak_cardinality is not None else 'unknown'})")
        lines.append(f"  record_downstream_cost = {getattr(g, 'record_downstream_cost', 0.0):g} fanout={getattr(g, 'record_downstream_fanout', 0)}")
        if getattr(g, "record_downstream_consumers", ()):
            lines.append("  record_downstream_consumers = " + ", ".join(f"{endpoint}->{child}:{cost:g}" for endpoint, child, cost in g.record_downstream_consumers))
        lines.append(f"  materialization_boundaries = {g.materialization_boundaries}")
        lines.append(f"  fused_internal_edges = {g.fused_internal_edges}")
        lines.append(f"  strategy_transitions = {g.strategy_transitions}")
        lines.append("  selectivity_estimates = " + ", ".join(f"{name}:{value:g}" for name, value in g.estimated_selectivities))
        lines.append("  downstream_pressure = " + ", ".join(f"{name}:{value:g}" for name, value in g.downstream_pressure))
        lines.append(f"  strategy_context_cost = {g.strategy_context_cost:g}")
        lines.append(f"  profile_transition_cost = {g.profile_transition_cost:g}")
        lines.append(f"  parallel_islands = {g.parallel_islands}")
        lines.append(f"  materialization_reuse_cost = {g.materialization_reuse_cost:g}")
        lines.append(f"  peak_live_cardinality = {g.peak_live_cardinality if g.peak_live_cardinality is not None else 'unknown'}")
        lines.append("  profile_signature = " + ", ".join(f"{name}:{memory}/{ordering}/{parallel}" for name, memory, ordering, parallel in g.profile_signature))
        lines.append(f"  execution_region_cost = {g.execution_region_cost:g}")
        lines.append("  execution_regions = " + ", ".join(f"{mode}:{size}:mixed={mixed}" for mode, size, mixed in g.execution_regions))
        lines.append(f"  global_strategy_search = {g.search_mode} evaluated={g.strategy_combinations_evaluated} space={g.strategy_search_space} optimality={g.global_optimality}")
    lines.append("  planning = complete")
    lines.append("  backend_constraints = applied" if False else "  backend_constraints = explicit-if-requested")
    lines.append("  runtime_execution = not-invoked")
    lines.append("  backend_lowering = separate-stage")
    lines.append("  deterministic = yes")
    lines.append("}")
    return "\n".join(lines)
