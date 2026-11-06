from slang.core import parse_file, run, show_expr_value


def test_text_and_list_runtime_values(tmp_path):
    source = '''
let names = ["Ada", "Grace", "Linus"]
let count = len(names)
let has_grace = contains(names, "Grace")
let text = join(names, ", ")
show count
show has_grace
show text
'''
    path = tmp_path / "text_list.sl"
    path.write_text(source, encoding="utf-8")
    program = parse_file(path)
    run(program)
    assert show_expr_value(program, program.show_exprs[0]) == "3"
    assert show_expr_value(program, program.show_exprs[1]) == "True"
    assert show_expr_value(program, program.show_exprs[2]) == "Ada, Grace, Linus"
