from slang.core import parse, run, validate


def execute(source):
    program = parse(source)
    validate(program)
    run(program)
    return program._bindings


def test_registry_pure_math_text_and_path():
    values = execute('''
result = replace(trim("  Hello  "), "Hello", "world")
number = sqrt(81)
path = join_path("data", "people.csv")
''')
    assert values["result"] == "world"
    assert values["number"] == 9
    assert values["path"] == "data/people.csv"


def test_registry_generic_collection_contracts():
    values = execute('''
let values = [3, 1, 2, 1]
reversed_values = reverse(values)
sorted_values = sort_numbers(values)
counted = count_value(values, 1)
''')
    assert values["reversed_values"] == [1, 2, 1, 3]
    assert values["sorted_values"] == [1, 1, 2, 3]
    assert values["counted"] == 2


def test_registry_json_roundtrip():
    values = execute('''
let source = "{\\"name\\":\\"Ada\\",\\"age\\":37}"
data = json_parse(source)
encoded = json_stringify(data)
''')
    assert values["data"]["name"] == "Ada"
    assert '"age":37' in values["encoded"]


def test_registry_is_used_by_semantic_inference():
    program = parse('result = reverse(["a", "b"])')
    validate(program)
    run(program)
    assert program._bindings["result"] == ["b", "a"]
