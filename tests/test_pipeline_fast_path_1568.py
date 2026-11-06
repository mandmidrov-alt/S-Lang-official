from slang.core import parse, run


def execute(source: str):
    program = parse(source)
    run(program)
    return program


def test_pipeline_fast_path_preserves_csv_result(tmp_path):
    data = tmp_path / "people.csv"
    data.write_text(
        "name,age,score,role\n"
        "a,17,100,engineer\n"
        "b,18,200,engineer\n"
        "c,21,300,artist\n"
        "d,30,400,engineer\n",
        encoding="utf-8",
    )
    p = execute(f'''let rows = read_csv("{data}")
adults = rows where to_number(item.age) >= 18
engineers = adults where item.role == "engineer"
scores = engineers map to_number(item.score)
total = scores reduce 0 with acc + item
show total
''')
    assert p._collections["total"] == 600


def test_pipeline_fast_path_handles_arithmetic_and_logical_conditions(tmp_path):
    data = tmp_path / "values.csv"
    data.write_text(
        "name,x,y\n"
        "a,2,3\n"
        "b,4,5\n"
        "c,1,9\n",
        encoding="utf-8",
    )
    p = execute(f'''let rows = read_csv("{data}")
selected = rows where to_number(item.x) * 2 >= 4 and to_number(item.y) < 6
values = selected map to_number(item.x) + to_number(item.y)
total = values reduce 0 with acc + item
show total
''')
    assert p._collections["total"] == 14
