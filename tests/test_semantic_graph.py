from slang.core import parse, validate
from slang.semantic_graph import build_semantic_graph, format_semantic_graph


def test_unified_graph_contains_collection_ops_and_goal():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 88
adults = people where age >= 18
ranked = adults sort by score desc
scores = ranked map score
total = scores sum item
best = choose candidate from ranked maximizing score
''')
    validate(p)
    graph = build_semantic_graph(p.ast)
    by = graph.by_result()
    assert by['adults'].kind == 'filter'
    assert by['ranked'].kind == 'sort'
    assert by['scores'].kind == 'map'
    assert by['total'].kind == 'aggregate'
    assert by['best'].kind == 'select'
    assert by['ranked'].dependencies == ('adults#1',)
    assert by['scores'].dependencies == ('ranked#1',)
    assert by['total'].dependencies == ('scores#1',)
    assert by['best'].dependencies == ('ranked#1',)
    assert graph.topological_order() == ('adults#1', 'ranked#1', 'best#1', 'scores#1', 'total#1')


def test_graph_reports_external_sources():
    p = parse('''
data people:
    Alice age 22 score 91
adults = people where age >= 18
''')
    validate(p)
    graph = build_semantic_graph(p.ast)
    assert graph.by_result()['adults'].external_sources == ('people',)


def test_graph_detects_cycles():
    p = parse('''
data a:
    Alice age 20 score 1
x = a map score
y = x map item + 1
''')
    validate(p)
    graph = build_semantic_graph(p.ast)
    assert graph.topological_order() == ('x#1', 'y#1')
    assert 'semantic.graph' in format_semantic_graph(graph)


def test_versioned_bindings_model_reassignment_as_separate_nodes():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 88
selected = people where age >= 18
selected sort by score desc
scores = selected map score
total = scores sum item
''')
    validate(p)
    graph = build_semantic_graph(p.ast)
    by = graph.by_binding()
    assert set(by) == {"selected#1", "selected#2", "scores#1", "total#1"}
    assert by["selected#2"].dependencies == ("selected#1",)
    assert by["scores#1"].dependencies == ("selected#2",)
    assert graph.topological_order() == ("selected#1", "selected#2", "scores#1", "total#1")


def test_rebinding_sort_depends_on_prior_map_of_same_name():
    p = parse('''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36)]
selected = people where row.age >= 20
ordered = selected map row.label
ordered = ordered sort by item asc
joined = ordered reduce "" with acc + item
''')
    validate(p)
    graph = build_semantic_graph(p.ast)
    by = graph.by_binding()
    assert by["ordered#2"].kind == "sort"
    assert by["ordered#2"].dependencies == ("ordered#1",)
    assert by["joined#1"].dependencies == ("ordered#2",)
    assert graph.topological_order() == (
        "selected#1", "ordered#1", "ordered#2", "joined#1"
    )
