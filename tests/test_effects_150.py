from slang.core import parse, validate
from slang.execution_ir import build_execution_ir
from slang.effect_analysis import analyze_effects, validate_strategy_effects
from slang.compiler_pipeline import compile_semantic_pipeline


def test_pure_map_is_effect_free():
    p = parse('''let values = [1, 2, 3]\nresult = values |> map * 2\nshow result\n''')
    validate(p)
    summaries = analyze_effects(build_execution_ir(p.ast))
    assert any(s.purity == "pure" for s in summaries)


def test_state_write_is_not_parallel_safe():
    p = parse('''state total = 0\nset total = total + 1\nshow total\n''')
    validate(p)
    summaries = analyze_effects(build_execution_ir(p.ast))
    writes = [s for s in summaries if "state-write" in s.effects]
    assert writes and all(not s.parallel_safe for s in writes)


def test_io_is_not_parallel_safe():
    p = parse('''let x = read("x.txt")\nshow x\n''')
    validate(p)
    summaries = analyze_effects(build_execution_ir(p.ast))
    io = [s for s in summaries if "io" in s.effects]
    assert io and all(not s.parallel_safe for s in io)


def test_pipeline_exposes_effects():
    p = parse('''let values = [1, 2, 3]\nresult = values |> map * 2\nshow result\n''')
    validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    assert pipeline.effects
    assert hasattr(pipeline, "effects")


def test_parallel_effect_validation_is_deterministic():
    p = parse('''state total = 0\nset total = total + 1\nshow total\n''')
    validate(p)
    ir = build_execution_ir(p.ast)
    class Choice:
        node = "@state:total:set:1#1"
        strategy = "parallel-map"
    errors = validate_strategy_effects(ir, (Choice(),))
    assert errors
