from pathlib import Path

from slang.core import parse, parse_file, validate, run, show_expr_value


def test_record_literal_access_and_helpers():
    source = '''let person = {name: "Ada", age: 36}
let name = person.name
let age = get(person, "age")
let present = has(person, "name")
let fields = keys(person)
show name
show age
show present
show fields
'''
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "Ada"
    assert show_expr_value(p, p.show_exprs[1]) == "36"
    assert show_expr_value(p, p.show_exprs[2]) == "True"
    assert show_expr_value(p, p.show_exprs[3]) == "['name', 'age']"


def test_record_list_literal_and_csv_relative_path(tmp_path):
    source_dir = tmp_path / "program"
    source_dir.mkdir()
    csv = source_dir / "people.csv"
    csv.write_text("name,age\nAda,36\nGrace,28\n", encoding="utf-8")
    program = source_dir / "main.sl"
    program.write_text('''let rows = read_csv("people.csv")
adults = rows where item.age >= "30"
names = adults map item.name
show names
show exists("people.csv")
''', encoding="utf-8")
    p = parse_file(program)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "['Ada']"
    assert show_expr_value(p, p.show_exprs[1]) == "True"
