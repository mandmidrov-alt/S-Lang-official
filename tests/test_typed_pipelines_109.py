from pathlib import Path
from slang.core import parse, validate, run


def test_typed_where_map_reduce_preserves_named_record_type():
    src = '''
record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 29)]
adults = people where age >= 18
names = adults map name
repacked = adults map Person(item.name, item.age)
summary = repacked reduce Person("none", 0) with Person(acc.name, acc.age + item.age)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)

    assert str(p._collection_types["people"]) == "List<Record<Person>>"
    assert str(p._collection_types["adults"]) == "List<Record<Person>>"
    assert str(p._collection_types["names"]) == "List<Text>"
    assert str(p._collection_types["repacked"]) == "List<Record<Person>>"
    assert str(p._collection_types["summary"]) == "Record<Person>"
    assert p._collections["names"] == ["Ada", "Lin"]
    assert p._collections["summary"]["age"] == 65


def test_nested_map_inference_is_recursive():
    src = '''
record Person:
    name: Text
    age: Number

let groups = [[Person("Ada", 36)], [Person("Bob", 15), Person("Lin", 29)]]
names = groups map item
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)

    assert str(p._collection_types["groups"]) == "List<List<Record<Person>>>"
    assert str(p._collection_types["names"]) == "List<List<Record<Person>>>"
