from slang.core import parse_file
from slang.core import validate, run


def execute(tmp_path, source):
    path = tmp_path / "main.sl"
    path.write_text(source, encoding="utf-8")
    program = parse_file(path)
    validate(program)
    run(program)
    return program


def test_frequency_number_is_stable(tmp_path):
    p = execute(tmp_path, '''
let xs = [2, 1, 2, 3, 1, 2]
let result = frequency(xs)
show result
''')
    assert p._bindings["result"] == [
        {"value": 2, "count": 3},
        {"value": 1, "count": 2},
        {"value": 3, "count": 1},
    ]


def test_frequency_text_and_boolean_are_type_preserving(tmp_path):
    p = execute(tmp_path, '''
let words = ["a", "b", "a", "c", "b"]
let flags = [true, false, true, true]
let word_freq = frequency(words)
let flag_freq = frequency(flags)
show word_freq
show flag_freq
''')
    assert p._bindings["word_freq"] == [
        {"value": "a", "count": 2},
        {"value": "b", "count": 2},
        {"value": "c", "count": 1},
    ]
    assert p._bindings["flag_freq"] == [
        {"value": True, "count": 3},
        {"value": False, "count": 1},
    ]


def test_frequency_empty_collection(tmp_path):
    p = execute(tmp_path, '''
let xs = []
let result = frequency(xs)
show result
''')
    assert p._bindings["result"] == []
