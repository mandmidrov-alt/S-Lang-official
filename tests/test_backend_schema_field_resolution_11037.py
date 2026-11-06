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

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
adults = people where row.age >= 18
values = adults map row.age
show values
'''


def test_native_backend_resolves_row_fields_from_schema_contract():
    program = parse(source())
    validate(program)
    ir = build_execution_ir(program.ast)
    contracts = list(ir.schema_contract())
    # Deliberately give the backend a schema that omits age. The AST still
    # contains row.age, so rejection proves the backend is using the semantic
    # schema contract rather than rediscovering the AST record declaration.
    fake = []
    for binding, inp, out in contracts:
        if binding == 'people#1':
            fake.append((binding, inp, RecordSchema('Person', (FieldSchema('name', 'Text'),))))
        else:
            fake.append((binding, inp, out))
    with pytest.raises(ValueError, match="no field 'age'"):
        llvm_ir(program, type_contract=ir.type_contract(), schema_contract=tuple(fake))
