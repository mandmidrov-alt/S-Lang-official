from pathlib import Path
import tempfile
from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir

def load(text):
    p=Path(tempfile.mktemp(suffix='.sl')); p.write_text(text)
    try:
        x=parse_file(p); validate(x); return x
    finally: p.unlink(missing_ok=True)

def test_state_read_is_explicit_and_depends_on_last_write():
    p=load('state x = 0\nlet a = x + 1\nset x = 10\nlet b = x + 1\n')
    ir=build_execution_ir(p.ast)
    reads=[n for n in ir.nodes if n.kind=='state:read']
    writes=[n for n in ir.nodes if n.kind in {'state:init','state:set'}]
    assert len(reads)==2
    assert all(n.effects==('state-read',) and n.access=='read-only' for n in reads)
    assert reads[0].dependencies==(writes[0].binding,)
    assert reads[1].dependencies==(writes[1].binding,)

def test_state_read_does_not_make_the_binding_itself_effectful():
    p=load('state x = 0\nlet a = x + 1\n')
    ir=build_execution_ir(p.ast)
    binding=next(n for n in ir.nodes if n.result=='a')
    assert binding.pure and binding.effects==()
    assert binding.dependencies==('@state:x:init#1', '@state:x:read:1')

def test_top_level_let_can_read_state():
    p=load('state x = 4\nlet a = x + 1\n')
    assert any(b.name == 'a' for b in p.ast.bindings)
