from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline, format_compiler_pipeline


def test_global_profile_model_is_exposed_and_deterministic():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    a = compile_semantic_pipeline(p.ast)
    b = compile_semantic_pipeline(p.ast)
    ga, gb = a.global_plan_cost, b.global_plan_cost
    assert ga is not None and gb is not None
    assert ga.profile_transition_cost >= 0
    assert ga.parallel_islands >= 0
    assert ga.materialization_reuse_cost >= 0
    assert ga.peak_live_cardinality is not None
    assert ga.profile_signature == gb.profile_signature
    assert ga == gb


def test_global_profile_diagnostics_are_printed():
    p = parse('''
data numbers:
    a value 1
    b value 2
filtered = numbers where value >= 1
mapped = filtered map value * 2
''')
    text = format_compiler_pipeline(compile_semantic_pipeline(p.ast))
    for field in (
        'profile_transition_cost', 'parallel_islands',
        'materialization_reuse_cost', 'peak_live_cardinality',
        'profile_signature',
    ):
        assert field in text
