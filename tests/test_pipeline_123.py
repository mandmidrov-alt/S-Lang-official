from pathlib import Path

from slang.core import parse_file, run, validate

ROOT = Path(__file__).resolve().parents[1]


def execute(name):
    p = parse_file(ROOT / "examples" / name)
    validate(p)
    run(p)
    return p


def test_pipeline_generic_record_chain():
    p = execute("pipeline_generic_records.sl")
    assert p._collections["result"] == 10


def test_pipeline_csv_filter_sort_map_average():
    p = execute("pipeline_csv_chain.sl")
    assert abs(p._collections["result"] - 91.66666666666667) < 1e-12


def test_pipeline_multiple_filters_map_sum():
    p = execute("pipeline_mixed_chain.sl")
    assert p._collections["result"] == 550
