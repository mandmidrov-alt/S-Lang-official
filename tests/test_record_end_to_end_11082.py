import subprocess
import sys
from pathlib import Path

from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir

ROOT = Path(__file__).resolve().parents[1]


def _optimized_source():
    return '''
record Person:
    id: Number
    score: Number
    bonus: Number
record R:
    id: Number
    value: Number

let people = [Person(1, 3, 10), Person(2, 5, 20)]
r1 = people map R(row.id, row.score * 2)
r2 = r1 map R(row.id, row.value + 1)
r3 = r2 map R(row.id, row.value + 3)
r4 = r2 map R(row.id, row.value * 2)
a = r3 map row.value
b = r4 map row.value
show a
show b
'''


def test_record_pipeline_is_consistent_end_to_end():
    module = parse(_optimized_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)

    plan = pipeline.selected_execution_plan.record_plan
    assert plan is not None
    assert pipeline.global_plan_cost.record_shared_recompute_decisions
    assert plan.record_shared_recompute_decisions == pipeline.global_plan_cost.record_shared_recompute_decisions
    assert plan.field_strategies == pipeline.global_plan_cost.record_field_strategies

    mlir = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    assert 'selected shared Record endpoint: r2' in mlir
    assert '@slang_record_f64_share(%v2)' in mlir
    assert 'record_shared_recompute' in mlir
    assert mlir.count('@slang_record_f64_share(%v2)') == 1
    assert '%v3 = func.call @slang_record_f64_map_field(%v2_materialized' in mlir
    assert '%v4 = func.call @slang_record_f64_map_field(%v2_materialized' in mlir


def test_native_record_pipeline_preserves_reference_semantics(tmp_path):
    source = tmp_path / 'reference.sl'
    executable = tmp_path / 'reference'
    source.write_text('''
record Person:
    id: Number
    score: Number
record R:
    id: Number
    value: Number

let people = [Person(1, 3), Person(2, 5)]
r1 = people map R(row.id, row.score * 2)
r2 = r1 map R(row.id, row.value + 1)
values = r2 map row.value
show values
''', encoding='utf-8')

    build = subprocess.run(
        [sys.executable, '-m', 'slang.cli', 'build', str(source), '-o', str(executable), '--backend', 'native'],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert build.returncode == 0, build.stderr

    run = subprocess.run([str(executable)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ['7', '11']
