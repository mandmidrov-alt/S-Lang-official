from pathlib import Path

from slang.core import parse, validate, run, show_expr_value


def test_csv_read_filter_map_reduce_and_headers(tmp_path, capsys):
    path = tmp_path / "people.csv"
    path.write_text("name,age\nAda,36\nGrace,28\nLinus,34\n", encoding="utf-8")
    source = f'''let rows = read_csv("{path.as_posix()}")
adults = rows where item.age >= "30"
ages = adults map to_number(item.age)
total = ages reduce 0 with acc + item
let headers = csv_headers(rows)
show total
show headers
'''
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "70"
    assert show_expr_value(p, p.show_exprs[1]) == "['name', 'age']"


def test_csv_write(tmp_path):
    path = tmp_path / "out.csv"
    source = f'''let rows = read_csv("{path.parent / 'input.csv'}")
let written = write_csv("{path}", rows)
show exists("{path}")
'''
    (path.parent / "input.csv").write_text("name,age\nAda,36\n", encoding="utf-8")
    p = parse(source)
    validate(p)
    run(p)
    assert path.read_text(encoding="utf-8") == "name,age\nAda,36\n"
