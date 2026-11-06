from pathlib import Path
from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir
from slang.execution_plan import build_execution_plan
from slang.strategy_selection import build_strategy_choices
from slang.cost_model import choose_by_cost
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
def ir_for(name):
 p=parse_file(ROOT/"examples"/name); validate(p); return build_execution_ir(p.ast)
def test_cost_model_is_deterministic():
 n=ir_for("data_generic.sl").nodes[0]; assert choose_by_cost(n,("generic","parallel-generic"))==choose_by_cost(n,("generic","parallel-generic"))
def test_small_known_collection_prefers_sequential():
 ir=ir_for("data_generic.sl"); n=ir.nodes[0]; d=choose_by_cost(n,("generic","scan-filter","parallel-filter")); assert d.selected == "scan-filter"

def test_large_known_collection_can_select_parallel():
 ir=ir_for("data_generic.sl"); n=ir.nodes[0]; large=replace(n, cardinality=100, cardinality_confidence="exact")
 d=choose_by_cost(large,("generic","scan-filter","parallel-filter")); assert d.selected == "parallel-filter"
def test_strategy_output_uses_cost_model():
 ir=ir_for("goal_ir.sl"); choices=build_strategy_choices(build_execution_plan(ir),ir); assert choices and all("cost model" in c.reason for c in choices)

def test_literal_filter_gets_exact_cardinality():
    ir=ir_for("data_generic.sl")
    n=next(x for x in ir.nodes if x.kind == "filter")
    assert n.cardinality == 3
    assert n.cardinality_confidence == "exact"

def test_data_shape_exposes_numeric_ranges_and_complexity():
    ir=ir_for("data_generic.sl")
    n=next(x for x in ir.nodes if x.kind == "filter")
    assert n.data_shape is not None
    assert ("age", 16.0, 31.0) in n.data_shape.numeric_ranges
    sort_ir=ir_for("data_generic.sl")
    sort=next(x for x in sort_ir.nodes if x.kind == "sort")
    assert sort.data_shape is not None and sort.data_shape.complexity == "nlogn"

def test_bounded_shape_uses_lower_bound_for_conservative_selection():
    from slang.execution_ir import DataShape
    ir = ir_for("data_generic.sl")
    n = ir.nodes[0]
    bounded = replace(n, data_shape=DataShape(2, 100, False, (), "linear", "test bound"), cardinality=None, cardinality_confidence="bounded")
    d = choose_by_cost(bounded, ("scan-filter", "parallel-filter"))
    assert d.selected == "scan-filter"
    assert d.estimates[0].work_lower is not None
    assert d.estimates[0].work_upper is not None


def test_exact_nlogn_work_grows_superlinearly():
    from slang.execution_ir import DataShape
    ir = ir_for("data_generic.sl")
    n = next(x for x in ir.nodes if x.kind == "sort")
    small = replace(n, data_shape=DataShape(10, 10, True, (), "nlogn", "test"), cardinality=10, cardinality_confidence="exact")
    large = replace(n, data_shape=DataShape(100, 100, True, (), "nlogn", "test"), cardinality=100, cardinality_confidence="exact")
    s = choose_by_cost(small, ("stable-sort",)).estimates[0]
    l = choose_by_cost(large, ("stable-sort",)).estimates[0]
    assert l.work > s.work * 5


def test_unknown_shape_keeps_base_model():
    ir = ir_for("data_generic.sl")
    n = replace(ir.nodes[0], data_shape=None, cardinality=None, cardinality_confidence="unknown")
    d = choose_by_cost(n, ("scan-filter", "parallel-filter"))
    assert d.estimates[0].work == 10
    assert d.confidence == "unknown"

def test_large_sort_can_select_parallel_stable_sort():
    from slang.execution_ir import DataShape
    from dataclasses import replace
    ir = ir_for("data_generic.sl")
    n = next(x for x in ir.nodes if x.kind == "sort")
    large = replace(n, data_shape=DataShape(1000, 1000, True, (), "nlogn", "test"), cardinality=1000, cardinality_confidence="exact")
    d = choose_by_cost(large, ("stable-sort", "parallel-stable-sort"))
    assert d.selected == "parallel-stable-sort"
