from slang.core import parse, run, validate, show_expr_value
from slang.semantic import TypeEnv, infer
from slang.core import parse_expr
from slang.types import ANY, RECORD, TEXT, list_type


def test_structured_data_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('pluck([{name: "Ada"}, {name: "Grace"}], "name")'), env) == list_type(ANY)
    assert infer(parse_expr('select_fields({name: "Ada", age: 36}, ["name"])'), env) == RECORD
    assert infer(parse_expr('merge_records({a: 1}, {b: 2})'), env) == RECORD
    assert infer(parse_expr('remove_field({a: 1}, "a")'), env) == RECORD


def test_structured_data_runtime():
    source = '''let people = [{name: "Ada", age: 36}, {name: "Grace", age: 28}]
let names = pluck(people, "name")
let person = {name: "Ada", age: 36}
let selected = select_fields(person, ["name"])
let merged = merge_records({name: "Ada"}, {age: 36})
let removed = remove_field(merged, "age")
show names
show selected
show merged
show removed
'''
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "['Ada', 'Grace']"
    assert show_expr_value(p, p.show_exprs[1]) == "{'name': 'Ada'}"
    assert show_expr_value(p, p.show_exprs[2]) == "{'name': 'Ada', 'age': 36}"
    assert show_expr_value(p, p.show_exprs[3]) == "{'name': 'Ada'}"
