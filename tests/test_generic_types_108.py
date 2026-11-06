from pathlib import Path
from slang.core import parse, validate, run


def test_generic_list_of_named_records_in_function_signature():
    src = '''
record Person:
    name: Text
    age: Number

function identity(people: List<Person>) -> List<Person>:
    return people

let people = [Person("Ada", 36)]
let selected = identity(people)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert str(p._collection_types["people"]) == "List<Record<Person>>"
    assert str(p._collection_types["selected"]) == "List<Record<Person>>"
    assert p._collections["selected"][0]["name"] == "Ada"


def test_nested_generic_lists_are_typed_recursively():
    src = '''
function identity(groups: List<List<Number>>) -> List<List<Number>>:
    return groups

let groups = [[1, 2], [3, 4]]
let result = identity(groups)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert str(p._collection_types["groups"]) == "List<List<Number>>"
    assert str(p._collection_types["result"]) == "List<List<Number>>"
    assert p._bindings["result"] == [[1, 2], [3, 4]]
