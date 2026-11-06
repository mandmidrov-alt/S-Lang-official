from pathlib import Path
from slang.core import parse, validate


def test_record_returning_function_can_flow_through_full_pipeline():
    src = '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Lin", 27, true)]

active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
ages = ordered map row.age
'''
    program = parse(src, Path.cwd())
    validate(program)
    assert str(program._collection_types['changed']) == 'List<Record<Person>>'
    assert str(program._collection_types['ordered']) == 'List<Record<Person>>'
    assert str(program._collection_types['ages']) == 'List<Number>'
