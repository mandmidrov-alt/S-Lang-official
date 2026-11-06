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

def test_same_state_read_write_conflict_is_ordered():
    ir=build_execution_ir(load('state x = 0\nlet a = x + 1\nset x = 10\n').ast)
    a=next(n for n in ir.nodes if n.result=='a')
    w=next(n for n in ir.nodes if n.kind=='state:set')
    assert a.memory_reads==('x',)
    assert w.memory_writes==('x',)
    s=build_schedule(ir)
    pos={k:i for i,k in enumerate(s.order)}
    assert pos[a.binding] < pos[w.binding]

def test_different_states_remain_independent():
    ir=build_execution_ir(load('state x = 0\nstate y = 0\nlet a = x + 1\nlet b = y + 1\n').ast)
    a=next(n for n in ir.nodes if n.result=='a')
    b=next(n for n in ir.nodes if n.result=='b')
    assert a.memory_reads==('x',) and b.memory_reads==('y',)
    s=build_schedule(ir)
    batch_for={name:i for i,batch in enumerate(s.batches) for name in batch}
    assert batch_for[a.binding] == batch_for[b.binding]

def test_read_read_same_state_does_not_conflict():
    ir=build_execution_ir(load('state x = 0\nlet a = x + 1\nlet b = x + 2\n').ast)
    reads=[n for n in ir.nodes if n.kind=='state:read']
    assert len(reads)==2
    assert reads[0].memory_reads==reads[1].memory_reads==('x',)
    s=build_schedule(ir)
    batch_for={name:i for i,batch in enumerate(s.batches) for name in batch}
    assert batch_for[reads[0].binding] == batch_for[reads[1].binding]
