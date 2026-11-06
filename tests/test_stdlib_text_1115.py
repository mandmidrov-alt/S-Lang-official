from slang.core import parse_file, run, show_expr_value


def run_source(tmp_path, source):
    path = tmp_path / "text_1115.sl"
    path.write_text(source, encoding="utf-8")
    program = parse_file(path)
    run(program)
    return program


def test_text_stdlib_expansion(tmp_path):
    program = run_source(tmp_path, '''
let a = contains_text("hello world", "world")
let b = index_of("hello world", "world")
let c = join_texts(["Ada", "Grace", "Linus"], ",")
let d = repeat_text("ab", 3)
show a
show b
show c
show d
''')
    assert [show_expr_value(program, x) for x in program.show_exprs] == ["True", "6", "Ada,Grace,Linus", "ababab"]


def test_text_stdlib_boundaries(tmp_path):
    program = run_source(tmp_path, '''
let a = contains_text("abc", "")
let b = index_of("abc", "z")
let c = join_texts([], "-")
let d = repeat_text("x", 0)
show a
show b
show c
show d
''')
    assert [show_expr_value(program, x) for x in program.show_exprs] == ["True", "-1", "", ""]
