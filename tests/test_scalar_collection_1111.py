from slang.core import parse_file, validate, run

def _run(tmp_path, source):
    src = tmp_path / "main.sl"
    src.write_text(source, encoding="utf-8")
    p = parse_file(src)
    validate(p)
    run(p)
    return p

def test_generic_first_last_distinct_number(tmp_path):
    p = _run(tmp_path, """
let xs = [3, 1, 3, 2]
let a = first(xs)
let b = last(xs)
let u = distinct(xs)
""")
    assert p._bindings["a"] == 3
    assert p._bindings["b"] == 2
    assert p._bindings["u"] == [3, 1, 2]

def test_generic_first_last_distinct_text(tmp_path):
    p = _run(tmp_path, """
let xs = ["Ada", "Bob", "Ada", "Lin"]
let a = first(xs)
let b = last(xs)
let u = distinct(xs)
""")
    assert p._bindings["a"] == "Ada"
    assert p._bindings["b"] == "Lin"
    assert p._bindings["u"] == ["Ada", "Bob", "Lin"]

def test_generic_first_last_distinct_boolean(tmp_path):
    p = _run(tmp_path, """
let xs = [true, false, true, false]
let a = first(xs)
let b = last(xs)
let u = distinct(xs)
""")
    assert p._bindings["a"] is True
    assert p._bindings["b"] is False
    assert p._bindings["u"] == [True, False]
