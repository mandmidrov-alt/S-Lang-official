import pytest
from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.backend import capabilities_for, validate_backend_type_contract


def test_backend_consumes_resolved_record_type_contract():
    src = '''
record Summary:
    name: Text
    value: Number

data people:
    Alice age 20 score 90
    Bob age 30 score 70
summaries = people map Summary("x", row.age + 1)
selected = summaries where row.value > 30
show selected
'''
    p = parse(src)
    validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    validate_backend_type_contract(pipeline, capabilities_for("native"))
    assert any(n.output_type == "List<Record<Summary>>" for n in pipeline.optimized_ir.nodes)


def test_backend_rejects_unadvertised_resolved_type_without_ast_reanalysis():
    src = '''
let values = [1, 2, 3]
result = values map item + 1
'''
    p = parse(src)
    validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    caps = capabilities_for("native")
    class Narrow:
        name = "narrow"
        def supports_type(self, type_name):
            return type_name == "Boolean"
    with pytest.raises(ValueError, match="resolved type"):
        validate_backend_type_contract(pipeline, Narrow())
