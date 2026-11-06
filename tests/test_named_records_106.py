from pathlib import Path
from slang.core import parse, validate, run, show_expr_value


def test_named_record_is_distinct_and_structured():
    src = '''
record Person:
    name: Text
    age: Number

let p = Person("Ada", 36)
let people = [p]
adults = people where age >= 18
names = adults map name
let written = write_csv("people.csv", people)
show p.name
show names
show keys(p)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "Ada"
    assert show_expr_value(p, p.show_exprs[1]) == "['Ada']"
    assert show_expr_value(p, p.show_exprs[2]) == "['name', 'age']"
    assert (Path.cwd() / "people.csv").exists()
    (Path.cwd() / "people.csv").unlink()


def test_named_record_parameter_typechecks():
    src = '''
record Person:
    name: Text
    age: Number

function adult(p: Person) -> Boolean:
    return p.age >= 18

let p = Person("Ada", 36)
let result = adult(p)
show result
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "True"


def test_different_named_records_are_not_interchangeable():
    src = '''
record Person:
    name: Text
    age: Number

record Planet:
    name: Text
    mass: Number

function adult(p: Person) -> Boolean:
    return p.age >= 18

let planet = Planet("Earth", 5)
let result = adult(planet)
'''
    p = parse(src, Path.cwd())
    import pytest
    with pytest.raises(TypeError, match="argument 1 of 'adult' expects Record<Person>, got Record<Planet>"):
        validate(p)
