from .ast import source_span_of
from .core import parse, validate, run, ir
from .goal_ir import GoalIR, lower_goals
from .goal_plan import GoalStrategy, GoalPlan, ExecutionPlan, analyze_goals, build_execution_plan
from .semantic_graph import SemanticNode, SemanticExecutionGraph, build_semantic_graph

from .execution_ir import ExecutionNode, ExecutionIR, build_execution_ir

from .memory_regions import MemoryRegion

from .alias_analysis import AliasFact, classify, relation, analyze_execution_ir

from .conflict_graph import ConflictEdge, build_conflict_graph

from .dependency_graph import DependencyEdge, DependencyGraph, build_dependency_graph

from .dependency_analysis import DependencyAnalysis, analyze_dependency_graph

from .execution_plan import ExecutionPlan, ExecutionPlanStep, build_execution_plan

from .strategy_selection import StrategyChoice, select_strategy, build_strategy_choices

from .cost_model import CostEstimate, CostDecision, choose_by_cost, rank_candidates

from .execution_optimizer import ExecutionOptimizationReport, optimize_execution_ir

from .compiler_pipeline import CompilerPipeline, compile_semantic_pipeline, compiler_artifact
from .compiler_artifact import CompilerArtifact, build_compiler_artifact

from .runtime_capability import RuntimeCapability, RuntimeCapabilityReport, audit_runtime_capability

from .stdlib_runtime import (
    RuntimeEffectPolicy, RuntimeCapabilityError, RuntimeExecutionProfile,
    runtime_effect_policy, runtime_execution_profile, current_runtime_effect_policy,
    registered_stdlib_effect, registered_stdlib_capability,
)

from .backend import lower_compiler_artifact, lower_backend_artifact

from .diagnostics import (
    Diagnostic, DiagnosticBag, DiagnosticSeverity, DiagnosticDefinition, SourcePosition, SourceSpan,
    diagnostic_definition, diagnostic_definitions, diagnostic_schema, diagnostic_schemas, validate_diagnostic_data,
    DIAGNOSTIC_PROTOCOL_NAME, DIAGNOSTIC_PROTOCOL_VERSION, diagnostic_to_protocol_dict, diagnostics_to_protocol_dict,
    serialize_diagnostic, serialize_diagnostics, deserialize_diagnostic, deserialize_diagnostics,
    diagnostic_to_lsp, diagnostics_to_lsp, diagnostics_to_lsp_publish, diagnostics_to_lsp_publish_documents, LSP_DIAGNOSTIC_SOURCE,
    diagnostics_for_source, format_diagnostic, format_diagnostics,
)
from .lsp_server import LSPDocument, LSPServer, LSP_SERVER_NAME, LSP_SERVER_VERSION

from .lsp_jsonrpc import (
    LSPJsonRpcServer, JsonRpcError, JsonRpcMessage, JsonRpcFramer, JSONRPC_VERSION, CONTENT_TYPE,
    PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR,
    make_response, make_notification, serialize_message, encode_message, decode_message,
)

from .lsp_process import LSPProcess, run_lsp_server
from .lsp_navigation import document_symbols, symbol_information, definition_candidates
from .lsp_features import hover, completion_items, signature_help

from .lsp_tokens import TOKEN_TYPES, TOKEN_MODIFIERS, semantic_tokens
