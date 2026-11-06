from slang.core import parse, run
from slang.optimizer import optimize_program


def _program():
    return parse('''
data values:
    a value 1
    b value 2
    c value 3
result = values |> where value >= 2 |> map value * 10
show result
''')


def test_filter_map_pipeline_is_fused():
    p = _program()
    report = optimize_program(p)
    assert report.pipeline_fusions == 1
    assert p._optimization_fused_pipelines['result'][0] == 'values'


def test_filter_map_fusion_preserves_result():
    p = _program()
    out = run(p)
    assert out._collections['result'] == [20, 30]


def test_filter_is_not_fused_when_result_is_reused():
    p = parse('''
data values:
    a value 1
    b value 2
    c value 3
filtered = values |> where value >= 2
result = filtered |> map value * 10
other = filtered |> map value + 1
show result
show other
''')
    report = optimize_program(p)
    assert report.pipeline_fusions == 0
    out = run(p)
    assert out._collections['result'] == [20, 30]
    assert out._collections['other'] == [3, 4]


def test_fusion_does_not_change_filter_map_types():
    p = _program()
    run(p)
    assert str(p._collection_types['result']) == 'List<Number>'
