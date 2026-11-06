from slang.core import parse_file, validate, run


def execute(tmp_path, source):
    path = tmp_path / "main.sl"
    path.write_text(source, encoding="utf-8")
    program = parse_file(path)
    validate(program)
    run(program)
    return program


def test_mode_number_is_most_frequent_and_stable_on_tie(tmp_path):
    p = execute(tmp_path, '''
let xs = [2, 1, 2, 3, 1]
let result = mode(xs)
show result
''')
    assert p._bindings["result"] == 2


def test_mode_preserves_text_and_boolean_types(tmp_path):
    p = execute(tmp_path, '''
let words = ["a", "b", "b", "a"]
let flags = [true, false, false, true, false]
let word_mode = mode(words)
let flag_mode = mode(flags)
show word_mode
show flag_mode
''')
    assert p._bindings["word_mode"] == "a"
    assert p._bindings["flag_mode"] is False


def test_mode_empty_collection_returns_none(tmp_path):
    p = execute(tmp_path, '''
let xs = []
let result = mode(xs)
show result
''')
    assert p._bindings["result"] is None
