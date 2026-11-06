from slang.core import parse, validate, llvm_ir
from slang.compiler_pipeline import compile_semantic_pipeline


def source():
    return '''
record Person:
    name: Text
    age: Number
    score: Number

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70), Person("Cara", 40, 95)]
mapped = people map row.score
show mapped
'''


def test_native_storage_uses_schema_contract():
    p = parse(source()); validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    ir = pipeline.optimized_ir
    text = llvm_ir(p, type_contract=ir.type_contract(), schema_contract=ir.schema_contract())
    assert '@rc_people_age' in text
    assert '@rc_people_score' in text
    assert 'field_values' not in text
    assert 'getelementptr inbounds' in text


def test_schema_contract_rejects_unknown_field_before_lowering():
    p = parse(source().replace('row.score', 'row.height'))
    try:
        validate(p)
    except TypeError as e:
        assert "unknown field 'height'" in str(e)
    else:
        raise AssertionError('unknown schema field was not rejected')
