from slang.core import parse, run, validate


def execute(source):
    program = parse(source)
    validate(program)
    run(program)
    return program


def test_collection_standard_library():
    p = execute("""
let xs = [5, 2, 2, 9]
let r = reverse(xs)
let sorted_values = sort_numbers(xs)
let total = sum_numbers(xs)
let smallest = min_number(xs)
let largest = max_number(xs)
let occurrences = count_value(xs, 2)
let generated = range_numbers(1, 6, 2)
let flags = [true, false, true]
let has_true = any_true(flags)
let all_flags = all_true(flags)
""")
    assert p._bindings["r"] == [9, 2, 2, 5]
    assert p._bindings["sorted_values"] == [2, 2, 5, 9]
    assert p._bindings["total"] == 18
    assert p._bindings["smallest"] == 2
    assert p._bindings["largest"] == 9
    assert p._bindings["occurrences"] == 2
    assert p._bindings["generated"] == [1, 3, 5]
    assert p._bindings["has_true"] is True
    assert p._bindings["all_flags"] is False


def test_reverse_preserves_generic_element_type():
    p = execute('let names = ["Ada", "Grace"]\nlet result = reverse(names)\n')
    assert p._bindings["result"] == ["Grace", "Ada"]
    assert str(p._collection_types["result"]) == "List<Text>"


def test_boolean_collection_contracts_are_checked():
    p = parse('let values = [true, false]\nlet result = any_true(values)\n')
    validate(p)
    assert p.ast is not None


def test_range_rejects_zero_step_at_runtime():
    p = parse('let values = range_numbers(1, 5, 0)\n')
    validate(p)
    try:
        run(p)
    except ValueError as exc:
        assert "step cannot be zero" in str(exc)
    else:
        raise AssertionError("expected zero-step range failure")


def test_range_rejects_non_finite_arguments():
    import math
    import pytest
    from slang.stdlib.collections import range_numbers

    for args in ((math.nan, 5, 1), (1, math.inf, 1), (1, 5, -math.inf)):
        with pytest.raises(ValueError, match="finite"):
            range_numbers(*args)


def test_range_rejects_non_numeric_and_boolean_arguments():
    import pytest
    from slang.stdlib.collections import range_numbers

    with pytest.raises(TypeError, match="numeric"):
        range_numbers(True, 5, 1)
    with pytest.raises(TypeError, match="numeric"):
        range_numbers(1, "5", 1)


def test_range_rejects_step_that_cannot_advance_float():
    import pytest
    from slang.stdlib.collections import range_numbers

    with pytest.raises(ValueError, match="too small to advance"):
        range_numbers(1e20, 1e20 + 1e6, 1)
