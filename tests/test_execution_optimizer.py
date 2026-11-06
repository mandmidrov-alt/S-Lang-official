from slang.execution_ir import ExecutionIR, ExecutionNode
from slang.execution_optimizer import optimize_execution_ir


def node(binding, deps=(), definition=False, pure=True, effects=()):
    return ExecutionNode(binding, "binding", binding, tuple(deps), (), pure,
                         definition, True, "read-only", False, tuple(effects),
                         (), (), (), (), None, "unknown", "", None)


def test_transitive_dependency_is_removed():
    ir = ExecutionIR((node("a"), node("b", ("a",)), node("c", ("a", "b"))))
    out, report = optimize_execution_ir(ir)
    assert report.transitive_dependencies_removed == 1
    assert out.by_binding()["c"].dependencies == ("b",)


def test_unreferenced_pure_definition_is_removed():
    ir = ExecutionIR((node("@fn:f", definition=True), node("use", ("@fn:g",))))
    out, report = optimize_execution_ir(ir)
    assert report.dead_definitions_removed == 1
    assert "@fn:f" not in out.by_binding()


def test_used_definition_is_kept():
    ir = ExecutionIR((node("@fn:f", definition=True), node("use", ("@fn:f",))))
    out, report = optimize_execution_ir(ir)
    assert report.dead_definitions_removed == 0
    assert "@fn:f" in out.by_binding()


def test_effectful_definition_is_never_removed():
    ir = ExecutionIR((node("@effect", definition=True, pure=False, effects=("IO",)),))
    out, report = optimize_execution_ir(ir)
    assert report.dead_definitions_removed == 0
    assert "@effect" in out.by_binding()


def test_data_shape_specialization_hints_are_deterministic():
    from slang.execution_ir import DataShape
    n = node("small", pure=True)
    n = ExecutionNode(n.binding, n.kind, n.result, n.dependencies, n.external_sources, n.pure, n.definition, n.deterministic, n.access, n.order_sensitive, n.effects, n.memory_reads, n.memory_writes, n.memory_regions, n.memory_region_specs, n.cardinality, n.cardinality_confidence, n.cardinality_reason, DataShape(3, 3, True, (), "linear", "test"))
    out, report = optimize_execution_ir(ExecutionIR((n,)))
    assert report.nodes_specialized == 1
    assert out.nodes[0].optimization_hints == ("small-cardinality",)


def test_nlogn_shape_gets_sort_specialization_hint():
    from slang.execution_ir import DataShape
    n = node("sort", pure=True)
    n = ExecutionNode(n.binding, "sort", n.result, n.dependencies, n.external_sources, n.pure, n.definition, n.deterministic, n.access, n.order_sensitive, n.effects, n.memory_reads, n.memory_writes, n.memory_regions, n.memory_region_specs, n.cardinality, n.cardinality_confidence, n.cardinality_reason, DataShape(100, 100, True, (), "nlogn", "test"))
    out, report = optimize_execution_ir(ExecutionIR((n,)))
    assert "large-cardinality" not in out.nodes[0].optimization_hints
    assert "nlogn-specialized" in out.nodes[0].optimization_hints
