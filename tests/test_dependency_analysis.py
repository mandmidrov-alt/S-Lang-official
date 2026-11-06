from pathlib import Path
from slang.core import parse_file, parse, validate
from slang.execution_ir import build_execution_ir
from slang.dependency_analysis import analyze_dependency_graph


def test_dependency_analysis_has_levels_and_critical_path():
    p = parse_file(Path('examples/goal_ir.sl'))
    validate(p)
    a = analyze_dependency_graph(build_execution_ir(p.ast))
    assert a.levels
    assert a.critical_path_length == len(a.critical_path)
    assert a.critical_path


def test_dependency_analysis_finds_parallel_read_only_goals():
    p = parse_file(Path('examples/goal_ir.sl'))
    validate(p)
    a = analyze_dependency_graph(build_execution_ir(p.ast))
    assert any(len(group) > 1 for group in a.parallel_candidates)
    assert any(len(group) > 1 for group in a.parallel_safe_candidates)


def test_dependency_analysis_detects_state_ordering():
    p = parse('state x = 0\nlet a = x + 1\nset x = 10\n')
    validate(p)
    a = analyze_dependency_graph(build_execution_ir(p.ast))
    positions = {n: i for i, level in enumerate(a.levels) for n in level}
    assert any('set' in n for n in positions)
    assert positions['a#1'] < positions[next(n for n in positions if ':set:' in n)]
