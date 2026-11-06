from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.optimizer import enumerate_record_plan_options


_BASE = """
record Person:
    name: Text
    age: Number
record R1:
    name: Text
    value: Number
record R2:
    name: Text
    value: Number
record R3:
    name: Text
    value: Number

let people = [Person("A", 20), Person("B", 30)]
r1 = people map R1(row.name, row.age + 1)
r2 = r1 map R2(row.name, row.value + 1)
r3 = r2 map R3(row.name, row.value + 1)
"""


def _compile(extra):
    module = parse(_BASE + extra)
    validate(module)
    return compile_semantic_pipeline(module.ast)


def test_intermediate_fanout_changes_global_record_plan():
    linear = _compile("show r3\n")
    branched = _compile(
        """
branch_a = r2 where row.value > 20
branch_b = r2 where row.value > 25
show r3
"""
    )

    assert linear.global_plan_cost.record_plan_mode == "full"
    assert branched.global_plan_cost.record_plan_mode == "partial"
    assert branched.global_plan_cost.record_plan.fused_segments == (
        ("people", "r1", "r2"),
        ("r2", "r3"),
    )


def test_high_fanout_can_select_full_materialization():
    branches_r1 = "\n".join(
        f"r1_branch_{i} = r1 where row.value > {20 + i}" for i in range(3)
    )
    branches_r2 = "\n".join(
        f"r2_branch_{i} = r2 where row.value > {20 + i}" for i in range(3)
    )
    pipeline = _compile(branches_r1 + "\n" + branches_r2 + "\nshow r3\n")

    assert pipeline.global_plan_cost.record_plan_mode == "materialized"
    assert pipeline.global_plan_cost.record_plan.fused_segments == (
        ("people", "r1"),
        ("r1", "r2"),
        ("r2", "r3"),
    )


def test_record_alternatives_remain_competing_candidates():
    source = """
branch_a = r2 where row.value > 20
branch_b = r2 where row.value > 25
show r3
"""
    pipeline = _compile(source)
    module = parse(_BASE + source)
    validate(module)
    options = enumerate_record_plan_options(type("P", (), {"ast": module.ast})())

    assert len(options) >= 3
    assert {option.mode for option in options} >= {"full", "partial", "materialized"}
    assert pipeline.global_plan_cost.record_plan_alternatives == len(options)
