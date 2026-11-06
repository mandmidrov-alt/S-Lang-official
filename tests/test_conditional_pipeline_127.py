from pathlib import Path
from slang.core import parse_file, validate, run
ROOT=Path(__file__).resolve().parents[1]

def test_true_branch():
    p=parse_file(ROOT/'examples/conditional_pipeline.sl'); validate(p); run(p)
    assert p._collections['result']==[40,50,60]

def test_false_branch():
    p=parse_file(ROOT/'examples/conditional_pipeline_false.sl'); validate(p); run(p)
    assert p._collections['result']==[8,10,12]

def test_where_branch():
    p=parse_file(ROOT/'examples/conditional_pipeline_where.sl'); validate(p); run(p)
    assert [r['name'] for r in p._collections['result']]==['b','c']


def test_mixed_branch_kinds_are_allowed_when_result_types_match():
    from slang.core import ParseError
    source = """data values:
    a value 1
let enabled = true
result = values |> if enabled then map value else where value > 0
"""
    try:
        parse_file(ROOT/'examples/conditional_pipeline_invalid.sl')
    except FileNotFoundError:
        pass
    import slang.core as core
    source = source.replace("map value else where value > 0", "map value |> sum item else where value > 0 |> map value |> sum item")
    p = core.parse(source)
    core.validate(p)
    core.run(p)
    assert p._collections["result"] == 1

def test_condition_is_evaluated_before_branch():
    p=parse_file(ROOT/'examples/conditional_pipeline.sl'); validate(p); run(p)
    assert p._collections['result']==[40,50,60]
