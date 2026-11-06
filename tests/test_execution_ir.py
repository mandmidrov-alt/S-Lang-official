import tempfile
from pathlib import Path
from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir
def load(text):
 p=Path(tempfile.mktemp(suffix='.sl'));p.write_text(text)
 try:x=parse_file(p);validate(x);return x
 finally:p.unlink(missing_ok=True)
def test_chain():
 p=load('data people:\n    Alice age 22 score 91\nadults = people where age >= 18\nscores = adults map score\ntotal = scores sum item\n');ir=build_execution_ir(p.ast)
 assert [n.kind for n in ir.nodes][-3:]==['filter','map','aggregate'];assert ir.topological_order()[-3:]==('adults#1','scores#1','total#1')
def test_function():
 p=load('function adjusted(x: Number) -> Number:\n    return x + 3\nlet value = adjusted(5)\n');ir=build_execution_ir(p.ast);assert any(n.binding=='@fn:adjusted' for n in ir.nodes);assert '@fn:adjusted' in next(n for n in ir.nodes if n.binding=='value#1').dependencies
def test_goal():
 p=load('data people:\n    Alice age 22 score 91\nbest = choose candidate from people maximizing score\n');ir=build_execution_ir(p.ast);assert next(n for n in ir.nodes if n.result=='best').kind=='goal:select'
