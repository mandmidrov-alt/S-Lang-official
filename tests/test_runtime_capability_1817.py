from pathlib import Path

from slang.compiler_pipeline import compile_semantic_pipeline
from slang import core
from slang.runtime_capability import audit_runtime_capability, format_runtime_capability

ROOT = Path(__file__).resolve().parents[1]


def compile_source(text):
    module = core.parse(text)
    core.validate(module)
    return module, compile_semantic_pipeline(module.ast)


def test_capability_report_marks_supported_unified_plan():
    module, pipeline = compile_source('''
function double(x: Number) -> Number:
    return x * 2

let values = [1, 2, 3]
result = values map double(item)
show result
''')
    report = audit_runtime_capability(pipeline)
    assert report.unified_supported
    assert not report.fallback_required
    assert report.supported_nodes == report.total_nodes
    assert pipeline.runtime_capability == report
    text = format_runtime_capability(report)
    assert 'unified_supported = yes' in text
    assert 'fallback_nodes = none' in text


def test_capability_report_identifies_generic_strategy_as_fallback_reason():
    module, pipeline = compile_source('''
let values = [1, 2, 3]
result = values map item + 1
show result
''')
    # Force an audit-only synthetic unsupported strategy without executing it.
    choice = next(s for s in pipeline.strategies if pipeline.optimized_ir.by_binding()[s.node].kind == 'map')
    from dataclasses import replace
    altered = tuple(replace(s, strategy='generic') if s.node == choice.node else s for s in pipeline.selected_execution_plan.steps)
    selected = replace(pipeline.selected_execution_plan, steps=altered)
    altered_pipeline = replace(pipeline, selected_execution_plan=selected)
    report = audit_runtime_capability(altered_pipeline)
    assert report.fallback_required
    entry = next(e for e in report.entries if e.node == choice.node)
    assert not entry.supported
    assert 'generic' in entry.reason


def test_compile_pipeline_exposes_capability_summary():
    module, pipeline = compile_source('''
let values = [1, 2]
show values
''')
    assert hasattr(pipeline, 'runtime_capability')
    assert pipeline.runtime_capability.total_nodes == pipeline.selected_execution_plan.operation_count
