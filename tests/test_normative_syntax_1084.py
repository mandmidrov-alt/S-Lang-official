"""Conformance tests for syntax documented in S-Lang 1.0.84."""

import pytest

from slang.core import parse, run, validate


@pytest.mark.parametrize(
    "source",
    [
        'let name = "Ada"\nlet age = 36\nshow name, age',
        'let score = 82\nlet grade = if score >= 90 then "A" else "B"\nshow grade',
        'function classify(score: Number) -> Text:\n    if score >= 90:\n        return "excellent"\n    else:\n        return "other"\nlet result = classify(92)\nshow result',
        'let values = [1, 2, 3]\nlet filtered = values where item >= 2\nlet doubled = filtered map item * 2\nlet total = doubled sum\nshow total',
        'let values = [3, 1, 2]\nsorted = values sort by item asc\nshow sorted',
        'let values = [1, 2, 3, 4]\nresult = values |> where >= 3 |> map item * 2 |> sum\nshow result',
        'sequence values from 1 for 5 steps using value * 2\nshow values',
        'state counter = 0\nset counter = counter + 1\nshow counter',
    ],
)
def test_documented_1084_syntax_parses(source):
    parse(source)


def test_top_level_block_if_is_supported_by_the_canonical_grammar():
    source = 'let score = 90\nif score >= 90:\n    show "excellent"\nelse:\n    show "other"'
    parse(source)


def test_sort_with_let_is_supported_and_preferred():
    parse('let values = [3, 1, 2]\nlet sorted = values sort by item asc\nshow sorted')


def test_pipeline_with_let_is_supported_and_preferred():
    parse('let values = [1, 2, 3, 4, 5]\nlet result = values |> where >= 3 |> map item * 2 |> sum\nshow result')


def test_lexical_variables_work_inside_collection_predicates_and_pipelines():
    source = """let values = [1, 2, 3, 4, 5]
let threshold = 3
let selected = values where item >= threshold
let doubled = selected map item * 2
let total = doubled sum
let sorted = values sort by item desc
let pipeline_total = values |> where >= threshold |> map item * 2 |> sum
show selected
show doubled
show total
show sorted
show pipeline_total
"""
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["selected"] == [3, 4, 5]
    assert program._collections["doubled"] == [6, 8, 10]
    assert program._collections["total"] == 24
    assert program._collections["sorted"] == [5, 4, 3, 2, 1]
    assert program._collections["pipeline_total"] == 24
