from slang.core import parse, show_expr_value
from slang.runtime import execute


def test_unified_runtime_executes_target_directed_transition():
    p = parse('''
state limit = 4
sequence path from 1 for up to 4 steps toward limit choosing:
    value + 1
    value + 2
    value + 3
    satisfy candidate <= limit
show path
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._collections["path"] == [1, 4]


def test_unified_runtime_allows_function_definition_nodes_in_mixed_plan():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
state threshold = 2
set threshold = threshold + 1
let values = [1, 2]
result = values |> map double
show result
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._states["threshold"] == 3
    assert show_expr_value(p, p.show_exprs[0]) == "[2, 4]"
