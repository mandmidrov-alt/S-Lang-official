from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline, format_compiler_pipeline

def test_whole_region_execution_modes_are_deterministic():
    p = parse('''
data numbers:
    a value 1
    b value 2
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    a = compile_semantic_pipeline(p.ast)
    b = compile_semantic_pipeline(p.ast)
    assert a.global_plan_cost is not None
    assert a.global_plan_cost.execution_regions == b.global_plan_cost.execution_regions
    assert a.global_plan_cost.execution_region_cost >= 0
    assert a.global_plan_cost == b.global_plan_cost

def test_whole_region_mode_diagnostics_are_exposed():
    p = parse('''
data numbers:
    a value 1
    b value 2
filtered = numbers where value >= 1
mapped = filtered map value * 2
''')
    text = format_compiler_pipeline(compile_semantic_pipeline(p.ast))
    assert 'execution_region_cost' in text
    assert 'execution_regions' in text
