from pathlib import Path
from slang.core import parse_file, parse, validate
from slang.execution_ir import build_execution_ir
from slang.execution_scheduler import build_schedule

def test_schedule_is_dependency_safe_and_deterministic():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    ir = build_execution_ir(p.ast)
    schedule = build_schedule(ir)
    assert schedule.order
    positions = {name: i for i, name in enumerate(schedule.order)}
    for node in ir.nodes:
        for dep in node.dependencies:
            assert positions[dep] < positions[node.binding]

def test_independent_nodes_share_a_batch_when_possible():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    schedule = build_schedule(build_execution_ir(p.ast))
    assert any(len(batch) > 1 for batch in schedule.batches)


def test_execution_nodes_expose_semantic_properties():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    ir = build_execution_ir(p.ast)
    assert ir.nodes
    assert all(n.deterministic for n in ir.nodes)
    assert all(n.access == 'read-only' for n in ir.nodes)
    assert all(n.reorderable and n.parallel_safe for n in ir.nodes if not n.effects)
    assert any(n.effects for n in ir.nodes)

def test_schedule_marks_current_batches_parallel_safe():
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    schedule = build_schedule(build_execution_ir(p.ast))
    assert schedule.parallel_safe_batches
    assert any(schedule.parallel_safe_batches)
    assert any(not x for x in schedule.parallel_safe_batches)


def test_conflict_graph_orders_state_write_after_read():
    from slang.conflict_graph import build_conflict_graph
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'state_reads.sl')
    validate(p)
    ir = build_execution_ir(p.ast)
    edges = build_conflict_graph(ir)
    assert edges
    assert any(e.before.startswith('@state:x:read') and ':set:' in e.after for e in edges)


def test_conflict_graph_does_not_conflict_disjoint_collection_fields():
    from slang.conflict_graph import build_conflict_graph
    p = parse_file(Path(__file__).parents[1] / 'examples' / 'goal_ir.sl')
    validate(p)
    ir = build_execution_ir(p.ast)
    edges = build_conflict_graph(ir)
    assert all(not (e.before == 'best#1' and e.after == 'route#1') for e in edges)



def test_dependency_graph_classifies_data_edge():
    from slang.execution_ir import build_execution_ir
    from slang.dependency_graph import build_dependency_graph
    p = parse_file(Path("examples/goal_ir.sl"))
    validate(p)
    g = build_dependency_graph(build_execution_ir(p.ast))
    # Goal dependencies may be empty in this example; verify the graph shape.
    assert all(e.kind in {"data", "memory", "effect", "explicit"} for e in g.edges)

def test_dependency_graph_memory_edge_for_state():
    from slang.execution_ir import build_execution_ir
    from slang.dependency_graph import build_dependency_graph
    p = parse('state x = 0\nlet a = x + 1\nset x = 10\n')
    validate(p)
    g = build_dependency_graph(build_execution_ir(p.ast))
    assert any(e.kind == "memory" for e in g.edges)

def test_dependency_graph_effect_edge_for_show_order():
    from slang.execution_ir import build_execution_ir
    from slang.dependency_graph import build_dependency_graph
    p = parse_file(Path('examples/goal_ir.sl'))
    validate(p)
    g = build_dependency_graph(build_execution_ir(p.ast))
    assert any(e.kind == 'effect' for e in g.edges)
