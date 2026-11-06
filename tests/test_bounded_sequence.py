from slang.core import parse, run, validate


def test_bounded_sequence_stops_on_condition():
    source = """
sequence values from 1 for up to 20 steps until value >= 100 using value * 3 + 1
total = values reduce 0 with acc + item
show values
show total
"""
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["values"] == [1, 4, 13, 40, 121]
    assert program._collections["total"] == 179


def test_bounded_sequence_respects_maximum_steps():
    source = "sequence values from 1 for up to 3 steps until value >= 100 using value * 3 + 1\nshow values\n"
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["values"] == [1, 4, 13]


def test_bounded_sequence_requires_boolean_condition():
    source = "sequence values from 1 for up to 3 steps until value + 1 using value * 3 + 1\n"
    program = parse(source)
    try:
        validate(program)
    except TypeError as exc:
        assert "until condition must be Boolean" in str(exc)
    else:
        raise AssertionError("expected Boolean until condition error")
