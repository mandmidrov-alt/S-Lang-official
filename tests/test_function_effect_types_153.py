import pytest
from slang.core import parse, validate
from slang.ast import TypeRef
from slang.types import function_type, NUMBER, TEXT, same_or_any, type_from_ref


def test_function_type_can_carry_pure_contract():
    t = function_type((NUMBER,), NUMBER, ())
    assert t.effects == ()
    assert str(t) == 'Function<Number, Number, pure>'


def test_function_type_contract_rejects_stronger_effect():
    pure = function_type((NUMBER,), NUMBER, ())
    io = function_type((NUMBER,), NUMBER, ('io',))
    allowed_io = function_type((NUMBER,), NUMBER, ('io',))
    assert not same_or_any(pure, io)
    assert same_or_any(allowed_io, pure)
    assert same_or_any(allowed_io, io)


def test_first_class_function_value_carries_inferred_effect_contract():
    p = parse('''
function load(path: Text) -> Text:
    return read(path)
let transform = load
let result = transform("x.txt")
''')
    validate(p)
    assert p is not None


def test_explicit_function_effect_type_syntax_is_supported():
    ref = TypeRef('Function', (TypeRef('Number'), TypeRef('Number'), TypeRef('pure')))
    t = type_from_ref(ref)
    assert t.effects == ('pure',)
    assert str(t) == 'Function<Number, Number, pure>'


def test_pure_function_parameter_rejects_io_function():
    p = parse('''
function io_double(x: Number) -> Number:
    let data = read("x.txt")
    return x
function apply_pure(f: Function<Number, Number, pure>) -> Number:
    return f(2)
let result = apply_pure(io_double)
''')
    with pytest.raises(TypeError, match="argument 1 of 'apply_pure'"):
        validate(p)

def test_compose_unions_function_effect_contracts():
    from slang.semantic import TypeEnv, infer
    from slang.ast import Call, Name
    pure = function_type((NUMBER,), NUMBER, ())
    io = function_type((NUMBER,), NUMBER, ('io',))
    env = TypeEnv(
        names={'pure_fn': pure, 'io_fn': io},
        fields={}, properties={}, functions={}
    )
    composed = infer(Call('compose', (Name('pure_fn'), Name('io_fn'))), env)
    assert composed.effects == ('io',)


def test_effect_contract_flows_through_function_alias_into_execution_ir():
    from slang.core import parse, validate
    from slang.execution_ir import build_execution_ir
    p = parse('''
function load(x: Text) -> Text:
    return read(x)
let transform = load
let values = ["a.txt"]
result = values |> map transform
''')
    validate(p)
    ir = build_execution_ir(p.ast)
    mapped = [n for n in ir.nodes if n.kind == 'map']
    assert mapped
    assert 'io' in mapped[0].effects
    assert not mapped[0].reorderable
