from slang.core import parse_file, validate, run


def _run(tmp_path, source):
    src = tmp_path / "main.sl"
    src.write_text(source, encoding="utf-8")
    p = parse_file(src)
    validate(p)
    run(p)
    return p


def test_chunk_number(tmp_path):
    p = _run(tmp_path, """
let xs = [1, 2, 3, 4, 5]
let out = chunk(xs, 2)
""")
    assert p._bindings["out"] == [[1, 2], [3, 4], [5]]


def test_chunk_text_and_empty(tmp_path):
    p = _run(tmp_path, """
let xs = ["a", "b", "c"]
let out = chunk(xs, 2)
let empty = chunk([], 3)
""")
    assert p._bindings["out"] == [["a", "b"], ["c"]]
    assert p._bindings["empty"] == []


def test_pairwise_number(tmp_path):
    p = _run(tmp_path, """
let xs = [10, 20, 30, 40]
let out = pairwise(xs)
""")
    assert p._bindings["out"] == [[10, 20], [20, 30], [30, 40]]


def test_pairwise_singleton_and_empty(tmp_path):
    p = _run(tmp_path, """
let one = pairwise([true])
let empty = pairwise([])
""")
    assert p._bindings["one"] == []
    assert p._bindings["empty"] == []


def test_chunk_rejects_non_positive_size(tmp_path):
    src = tmp_path / "main.sl"
    src.write_text("let out = chunk([1, 2], 0)\n", encoding="utf-8")
    p = parse_file(src)
    validate(p)
    try:
        run(p)
    except RuntimeError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("chunk must reject non-positive sizes")
