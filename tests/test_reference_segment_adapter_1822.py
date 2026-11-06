from types import SimpleNamespace

from slang.core import parse
from slang.execution_ir import build_execution_ir
from slang.reference_runtime import segment_executor
from slang.segment_bridge import capture


def test_reference_binding_segment_executes_only_assigned_binding():
    module = parse("""
let a = 2
let b = a + 3
""")
    module._bindings = {"a": 2}
    module._collections = {}
    module._states = {}
    module.entities = {}
    ir = build_execution_ir(module.ast)
    bnode = next(node.binding for node in ir.nodes if node.kind == "binding" and node.result == "b")
    segment = SimpleNamespace(index=1, mode="reference-interpreter", nodes=(bnode,))
    handoff = capture(module, 1, "reference-interpreter")

    segment_executor(module, segment, handoff)
    assert module._bindings["a"] == 2
    assert module._bindings["b"] == 5


def test_reference_binding_adapter_does_not_execute_unassigned_nodes():
    module = parse("""
let a = 2
let b = a + 3
""")
    module._bindings = {}
    module._collections = {}
    module._states = {}
    module.entities = {}
    ir = build_execution_ir(module.ast)
    anode = next(node.binding for node in ir.nodes if node.kind == "binding" and node.result == "a")
    segment = SimpleNamespace(index=0, mode="reference-interpreter", nodes=(anode,))
    handoff = capture(module, 0, "reference-interpreter")

    segment_executor(module, segment, handoff)
    assert module._bindings == {"a": 2}
    assert "b" not in module._bindings


def test_unknown_reference_segment_kind_fails_explicitly():
    module = parse("let a = 2")
    ir = build_execution_ir(module.ast)
    segment = SimpleNamespace(index=0, mode="reference-interpreter", nodes=("@unsupported",))
    handoff = capture(module, 0, "reference-interpreter")
    try:
        segment_executor(module, segment, handoff)
    except RuntimeError as exc:
        assert "no reference segment adapter" in str(exc)
    else:
        raise AssertionError("unsupported reference segment must fail explicitly")


def test_reference_group_segment_uses_shared_collection_namespace():
    module = parse('''
let people = [{team: "A", score: 10}, {team: "B", score: 5}, {team: "A", score: 20}]
let groups = group_by(people, "team")
''')
    module._bindings = {}
    module._collections = {
        "people": [
            {"team": "A", "score": 10},
            {"team": "B", "score": 5},
            {"team": "A", "score": 20},
        ]
    }
    module._states = {}
    module.entities = {}
    ir = build_execution_ir(module.ast)
    group_node = next(node.binding for node in ir.nodes if node.kind == "group" and node.result == "groups")
    segment = SimpleNamespace(index=1, mode="reference-interpreter", nodes=(group_node,))
    handoff = capture(module, 1, "reference-interpreter")

    segment_executor(module, segment, handoff)

    assert "groups" in module._collections
    assert len(module._collections["groups"]) == 2
    assert module._collections["groups"][0]["key"] == "A"
