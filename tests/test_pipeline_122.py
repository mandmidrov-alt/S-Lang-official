from pathlib import Path
from slang.core import parse_file, validate, run

ROOT = Path(__file__).resolve().parents[1]


def execute(name):
    p = parse_file(ROOT / 'examples' / name)
    validate(p)
    run(p)
    return p


def test_pipeline_filter_sort_map():
    p = execute('pipeline.sl')
    assert p._collections['result'] == [96, 94, 88]


def test_pipeline_matches_expanded_operations():
    p = execute('pipeline_expanded.sl')
    assert p._collections['result'] == [96, 94, 88]


def test_pipeline_aggregate():
    p = execute('pipeline_aggregate.sl')
    assert p._collections['total'] == 278
