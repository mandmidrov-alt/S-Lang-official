from pathlib import Path
import pytest
from slang.core import parse, parse_file, validate, run
ROOT=Path(__file__).resolve().parents[1]


def test_then_branch_chain():
    p=parse_file(ROOT/'examples/conditional_pipeline_chain.sl'); validate(p); run(p)
    assert p._collections['result'] == 90


def test_else_branch_chain():
    p=parse_file(ROOT/'examples/conditional_pipeline_chain_false.sl'); validate(p); run(p)
    assert p._collections['result'] == 7


def test_branches_can_have_different_stage_kinds_with_compatible_result():
    source='''data values:\n    a value 1\n    b value 2\n    c value 3\nlet enabled = true\nresult = values |> if enabled then where value >= 2 |> map value * 10 |> sum item else where value >= 2 |> reduce 0 with acc + value\n'''
    p=parse(source); validate(p); run(p)
    assert p._collections['result'] == 50


def test_incompatible_branch_results_are_rejected():
    source='''data values:\n    a value 1\n    b value 2\nlet enabled = true\nresult = values |> if enabled then where value >= 1 |> map value * 10 else where value >= 1 |> reduce 0 with acc + value\n'''
    with pytest.raises(TypeError, match='compatible types'):
        validate(parse(source))


def test_empty_conditional_branch_is_rejected():
    source='''data values:\n    a value 1\nlet enabled = true\nresult = values |> if enabled then where value > 0 else \n'''
    with pytest.raises(Exception):
        parse(source)


def test_selected_branch_only_executes():
    source='''data values:\n    a value 1\n    b value 2\nlet enabled = false\nresult = values |> if enabled then reduce 0 with acc / 0 else sum value\n'''
    p=parse(source); validate(p); run(p)
    assert p._collections['result'] == 3


def test_conditional_can_be_followed_by_outer_pipeline():
    source='''data values:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\nlet enabled = true\nresult = values |> if enabled then (where value >= 2 |> map value * 10) else (where value >= 3 |> map value * 2) |> sum item\n'''
    p=parse(source); validate(p); run(p)
    assert p._collections['result'] == 90


def test_conditional_outer_pipeline_runs_after_selected_branch():
    source='''data values:\n    a value 1\n    b value 2\n    c value 3\nlet enabled = false\nresult = values |> if enabled then (map value * 10) else (map value * 2) |> where item >= 4 |> sum item\n'''
    p=parse(source); validate(p); run(p)
    assert p._collections['result'] == 10


def test_nested_branch_chain_and_outer_chain_types_are_checked():
    source='''data values:\n    a value 1\n    b value 2\nlet enabled = true\nresult = values |> if enabled then (map value * 10) else (map value) |> map item + 1\n'''
    p=parse(source); validate(p); run(p)
    assert p._collections['result'] == [11, 21]
