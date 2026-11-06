from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline


def test_execution_plan_and_selected_plan_preserve_ir_type_contract():
    src = '''
record Summary:
    name: Text
    value: Number

data people:
    Alice age 20 score 90
    Bob age 30 score 70

adults = people where row.age >= 18
summaries = adults map Summary("x", row.age + 1)
selected = summaries where row.value > 30
show selected
'''
    p = parse(src)
    validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    ir_by = pipeline.optimized_ir.by_binding()
    plan_by = {n: step for step in pipeline.execution_plan.steps for n in step.nodes}
    selected_by = pipeline.selected_execution_plan.by_node()
    for name in ("adults", "summaries", "selected"):
        binding = next(n.binding for n in pipeline.optimized_ir.nodes if n.result == name)
        assert plan_by[binding].input_type == ir_by[binding].input_type
        assert plan_by[binding].output_type == ir_by[binding].output_type
        assert selected_by[binding].input_type == ir_by[binding].input_type
        assert selected_by[binding].output_type == ir_by[binding].output_type
        assert (binding, ir_by[binding].input_type, ir_by[binding].output_type) in plan_by[binding].type_contracts
        assert (binding, ir_by[binding].input_type, ir_by[binding].output_type) in selected_by[binding].type_contracts

