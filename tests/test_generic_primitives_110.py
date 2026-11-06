from pathlib import Path
from slang.core import parse_file, validate, run
from slang.semantic import infer, TypeEnv
from slang.types import NUMBER, TEXT, list_type, type_var, generic_match, substitute_type


def test_generic_type_matching_is_recursive():
    bindings = {}
    assert generic_match(list_type(type_var('$T')), list_type(NUMBER), bindings)
    assert substitute_type(list_type(type_var('$T')), bindings) == list_type(NUMBER)


def test_generic_collection_builtins_typecheck_and_run(tmp_path):
    src = tmp_path / 'main.sl'
    src.write_text('''\nlet xs = [1, 2, 3]\nlet ys = append(xs, 4)\nlet a = first(ys)\nlet b = last(ys)\nlet nested = [[1, 2], [3]]\nlet flat = flatten(nested)\nshow a\nshow b\nshow flat\n''', encoding='utf-8')
    program = parse_file(src)
    validate(program)
    run(program)


def test_generic_record_collection_result_keeps_element_type(tmp_path):
    src = tmp_path / 'main.sl'
    src.write_text('''\nrecord Person:\n    name: Text\n    age: Number\n\nlet people = [Person("Ada", 36), Person("Bob", 15)]\nages = people map age\nlet expanded = append([1, 2], 42)\n''', encoding='utf-8')
    program = parse_file(src)
    validate(program)
    assert program._collection_types['expanded'].name == 'List'
    assert program._collection_types['expanded'].args[0] == NUMBER


def test_generic_argument_mismatch_is_rejected(tmp_path):
    src = tmp_path / 'main.sl'
    src.write_text('let xs = [1, 2]\nlet bad = append(xs, "text")\n', encoding='utf-8')
    program = parse_file(src)
    try:
        validate(program)
    except TypeError as exc:
        assert "append" in str(exc)
    else:
        raise AssertionError("expected generic type mismatch")
