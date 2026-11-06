from pathlib import Path
import tempfile
from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir
from slang.execution_scheduler import build_schedule

def load(text):
    p=Path(tempfile.mktemp(suffix='.sl')); p.write_text(text)
    try:
        x=parse_file(p); validate(x); return x
    finally: p.unlink(missing_ok=True)

def test_collection_field_regions_are_element_level():
    ir=build_execution_ir(load('''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\nadults = people where age >= 18\nscores = adults map score\n''').ast)
    f=next(n for n in ir.nodes if n.kind=='filter')
    m=next(n for n in ir.nodes if n.kind=='map')
    assert f.memory_regions == ('people[*].age',)
    assert m.memory_regions == ('adults[*].score',)

def test_different_collection_elements_can_be_independent():
    ir=build_execution_ir(load('''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\na = people map age\nb = people map score\n''').ast)
    nodes=[n for n in ir.nodes if n.kind=='map']
    assert nodes[0].memory_regions == ('people[*].age',)
    assert nodes[1].memory_regions == ('people[*].score',)
    s=build_schedule(ir)
    batches={k:i for i,b in enumerate(s.batches) for k in b}
    assert batches[nodes[0].binding] == batches[nodes[1].binding]

def test_whole_collection_region_conflicts_with_field_region():
    ir=build_execution_ir(load('''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\na = people map item\nb = people map score\n''').ast)
    nodes=[n for n in ir.nodes if n.kind=='map']
    assert nodes[0].memory_regions == ('people[*]',)
    assert nodes[1].memory_regions == ('people[*].score',)
    s=build_schedule(ir)
    batches={k:i for i,b in enumerate(s.batches) for k in b}
    assert batches[nodes[0].binding] != batches[nodes[1].binding]
