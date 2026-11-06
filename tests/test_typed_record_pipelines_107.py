from pathlib import Path

from slang.core import parse, validate, run


def test_named_record_type_survives_filter_sort_and_identity_map():
    src = '''
record Person:
    name: Text
    age: Number

let ada = Person("Ada", 36)
let bob = Person("Bob", 15)
let people = [ada, bob]
adults = people where age >= 18
ordered = adults sort by age desc
kept = ordered map item
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert str(p._collection_types["people"]) == "List<Record<Person>>"
    assert str(p._collection_types["adults"]) == "List<Record<Person>>"
    assert str(p._collection_types["ordered"]) == "List<Record<Person>>"
    assert str(p._collection_types["kept"]) == "List<Record<Person>>"
    assert [x["name"] for x in p._collections["kept"]] == ["Ada"]
    assert all(getattr(x, "type_name", None) == "Person" for x in p._collections["kept"])


def test_named_record_type_survives_map_to_record_function():
    src = '''
record Person:
    name: Text
    age: Number

function same_person(p: Person) -> Person:
    return p

let p = Person("Ada", 36)
let people = [p]
cloned = people map same_person(item)
'''
    program = parse(src, Path.cwd())
    validate(program)
    run(program)
    assert str(program._collection_types["cloned"]) == "List<Record<Person>>"
    assert program._collections["cloned"][0].type_name == "Person"
