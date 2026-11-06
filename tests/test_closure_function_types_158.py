from slang.core import parse
from slang.function_effects import analyze_function_effects
from slang.semantic import TypeEnv, infer, infer_block, _nested_decl_type
from slang.types import function_effects, function_type, is_function
from slang.ast import Call


def make_env(source):
    module = parse(source).ast
    contracts = {s.function: s.effects for s in analyze_function_effects(module)}
    fn = module.functions[0]
    env = TypeEnv(
        names={name: _nested_decl_type(ref) for name, ref in fn.parameters},
        fields={"Row": {}}, properties={}, functions={},
        function_effect_contracts=contracts, scope_prefix=fn.name
    )
    return module, fn, env


def test_nested_closure_function_type_contains_inferred_effect():
    module, fn, env = make_env('''
function make_loader() -> Function<Text, Text>:
    function load(path: Text) -> Text:
        return read(path)
    return load
''')
    inferred = infer_block(fn.body, env)
    assert is_function(inferred)
    assert function_effects(inferred) == ("io",)


def test_factory_result_effect_flows_into_alias_type():
    source = '''
function make_loader() -> Function<Text, Text>:
    function load(path: Text) -> Text:
        return read(path)
    return load
'''
    module, fn, env = make_env(source)
    returned = infer_block(fn.body, env)
    env.functions[fn.name] = ((), returned)
    env.names[fn.name] = function_type((), returned, ())
    loader = infer(Call('make_loader', ()), env)
    assert is_function(loader)
    assert function_effects(loader) == ("io",)


def test_pure_returned_closure_has_pure_function_contract():
    module, fn, env = make_env('''
function make(factor: Number) -> Function<Number, Number>:
    function multiply(x: Number) -> Number:
        return x * factor
    return multiply
''')
    inferred = infer_block(fn.body, env)
    assert function_effects(inferred) == ()
