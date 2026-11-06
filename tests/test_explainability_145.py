from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.explainability import format_execution_explanation
from slang.execution_profile import ExecutionProfile


def compile_source(source, **kwargs):
    p = parse(source)
    validate(p)
    return compile_semantic_pipeline(p.ast, **kwargs)


def test_explanation_records_selected_strategy_and_reason():
    result = compile_source('''
let values = [1, 2, 3]
result = values |> map * 2
''')
    step = result.execution_explanation.steps[-1]
    assert step.selected
    assert step.reason
    assert step.selected_score is not None


def test_explanation_is_deterministic():
    source = '''
let values = [1, 2, 3, 4]
result = values |> where >= 2 |> map * 2
'''
    a = compile_source(source).execution_explanation
    b = compile_source(source).execution_explanation
    assert a == b
    assert a.deterministic


def test_explanation_reports_backend_rejections():
    result = compile_source('''
let values = [1, 2, 3, 4]
result = values |> map * 2
''', backend_parallelism=("sequential",))
    step = result.execution_explanation.steps[-1]
    assert any(name == "parallel-map" for name, _ in step.rejected)
    assert "parallelism=parallel-where-independent unsupported" in dict(step.rejected)["parallel-map"]


def test_explanation_reports_profile():
    profile = ExecutionProfile(cpu_cores=4, allow_parallelism=True)
    result = compile_source('''
let values = [1, 2, 3]
result = values |> map * 2
''', execution_profile=profile)
    assert result.execution_explanation.execution_profile == profile


def test_explanation_formatter_is_human_readable():
    result = compile_source('''
let values = [1, 2, 3]
result = values |> map * 2
''')
    text = format_execution_explanation(result.execution_explanation)
    assert "execution.explain" in text
    assert "selected =" in text
    assert "why =" in text
    assert "considered =" in text
    assert "deterministic = yes" in text


def test_reference_profile_explains_parallel_rejection_without_backend_capabilities():
    result = compile_source('''
let values = [1, 2, 3]
result = values |> map * 2
''')
    step = result.execution_explanation.steps[-1]
    assert step.selected != "parallel-map"
    assert any(name == "parallel-map" for name, _ in step.rejected)
