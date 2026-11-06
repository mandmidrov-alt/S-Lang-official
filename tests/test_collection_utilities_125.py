from pathlib import Path
from slang.core import parse_file, validate, run

ROOT = Path(__file__).resolve().parents[1]


def execute(name):
    p = parse_file(ROOT / 'examples' / name)
    validate(p)
    run(p)
    return p


def test_distinct_take_skip():
    p = execute('collection_utilities_125.sl')
    assert p._bindings['unique'] == [3, 1, 2, 4, 5]
    assert p._bindings['head'] == [3, 1, 2]
    assert p._bindings['tail'] == [2, 4, 5]


def test_generic_types_for_collection_utilities():
    p = parse_file(ROOT / 'examples' / 'collection_utilities_125.sl')
    validate(p)
    assert str(p._collection_types['unique']) == 'List<Number>'
    assert str(p._collection_types['head']) == 'List<Number>'
    assert str(p._collection_types['tail']) == 'List<Number>'
