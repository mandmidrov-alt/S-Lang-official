from slang.core import parse, run
from slang.optimizer import optimize_program


def test_filter_map_sum_terminal_fusion():
    p = parse('''
data values:
    a value 1
    b value 2
    c value 3
    d value 4
result = values |> where value >= 2 |> map value * 10 |> sum
show result
''')
    report = optimize_program(p)
    assert report.pipeline_fusions >= 1
    fused = p._optimization_fused_terminals['result']
    assert fused[0] == 'values'
    assert [f.result for f in fused[1]] == ['__pipe_7_0']
    assert [m.result for m in fused[2]] == ['__pipe_7_1']
    out = run(p)
    assert out._collections['result'] == 90


def test_map_sum_terminal_fusion():
    p = parse('''
data values:
    a value 1
    b value 2
    c value 3
result = values |> map value * 2 |> sum
show result
''')
    report = optimize_program(p)
    assert report.pipeline_fusions >= 1
    out = run(p)
    assert out._collections['result'] == 12


def test_fused_terminal_does_not_materialize_intermediate_map():
    p = parse('''
data values:
    a value 1
    b value 2
result = values |> map value * 10 |> sum
''')
    run(p)
    assert 'result_mapped' not in p._collections
    assert p._collections['result'] == 30


def test_terminal_fusion_is_disabled_when_intermediate_is_observed():
    p = parse('''
data values:
    a value 1
    b value 2
mapped = values |> map value * 10
result = mapped |> sum
show mapped
show result
''')
    report = optimize_program(p)
    assert 'result' not in p._optimization_fused_terminals
    out = run(p)
    assert out._collections['mapped'] == [10, 20]
    assert out._collections['result'] == 30


def test_fused_average_matches_regular_semantics():
    p = parse('''
data values:
    a value 1
    b value 2
    c value 3
result = values |> where value > 1 |> map value * 2 |> average
''')
    out = run(p)
    assert out._collections['result'] == 5
