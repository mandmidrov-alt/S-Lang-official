import pytest
from slang.core import parse, validate, llvm_ir
from slang.execution_ir import build_execution_ir
from slang.types import RecordSchema, FieldSchema


def source():
    return '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
summaries = people map Summary(row.name, row.score - row.age)
selected = summaries where row.value >= 50
values = selected map row.value
show values
'''


def test_intermediate_record_storage_uses_output_schema():
    p = parse(source())
    validate(p)
    ir = build_execution_ir(p.ast)
    text = llvm_ir(p, type_contract=ir.type_contract(), schema_contract=ir.schema_contract())
    # Summary storage is a new layout, not a reuse of the Person layout.
    assert '%rcmbuf_1_label' in text
    assert '%rcmbuf_1_value' in text
    # The following filter reads the transformed Summary layout.
    assert '%rc_ptr_2_value' in text
    assert '%rc_ptr_2_age' not in text


def test_intermediate_record_schema_mismatch_is_rejected_before_lowering():
    p = parse(source())
    validate(p)
    ir = build_execution_ir(p.ast)
    fake = []
    for binding, inp, out in ir.schema_contract():
        if binding == 'summaries#1':
            fake.append((binding, inp, RecordSchema('Summary', (FieldSchema('label', 'Text'), FieldSchema('amount', 'Number')))))
        else:
            fake.append((binding, inp, out))
    with pytest.raises(ValueError, match="schema contract for 'summaries'"):
        llvm_ir(p, type_contract=ir.type_contract(), schema_contract=tuple(fake))
