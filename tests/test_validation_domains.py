from pathlib import Path
import sys
sys.path.insert(0,'.')
from slang.core import parse, validate, run, show_value


def test_data_pipeline():
    p=parse(Path('benchmarks/data/filter_sort.sl').read_text())
    validate(p); run(p)
    assert show_value(p,'adults','__value__') == '[Alice(22), Eve(25), Carol(31)]'


def test_geometry_units_and_formula():
    p=parse(Path('benchmarks/geometry/circle.sl').read_text())
    validate(p); run(p)
    assert show_value(p,'disk','area') == '314.159265358979 m2'
    assert show_value(p,'disk','circumference') == '62.8318530717959 m'


def test_geometry_rejects_bad_units():
    bad='circle disk:\n    radius 10 kg\n'
    try:
        validate(parse(bad))
    except TypeError:
        return
    assert False

def test_generic_data_pipeline_not_people_specific():
    p=parse(Path('examples/data_generic.sl').read_text())
    validate(p); run(p)
    assert show_value(p,'adults','__value__') == '[Alice(age=22, score=91), Carol(age=31, score=95), Eve(age=25, score=90)]'
    assert p.ast.datasets[0].name == 'students'
    assert p.ast.filters[0].predicate.expr.op == '>='
    assert p.ast.sorts[0].spec.expr.op == '/'
