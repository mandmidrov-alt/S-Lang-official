#!/usr/bin/env python3
import argparse, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from slang.core import parse, validate, llvm_ir

ap=argparse.ArgumentParser()
ap.add_argument('source')
ap.add_argument('-o','--output',default='program')
ap.add_argument('--keep-llvm',action='store_true')
a=ap.parse_args()
src=Path(a.source); out=Path(a.output)
p=parse(src.read_text()); validate(p)
ll=out.with_suffix('.ll')
ll.write_text(llvm_ir(p))
runtime = Path(__file__).parent / 'slang' / 'slang_runtime.c'
cmd=['clang','-O2','-x','ir',str(ll),'-x','c',str(runtime), *(['-lm'] if sys.platform != 'win32' else []), '-o', str(out)]
try:
    subprocess.run(cmd,check=True)
except FileNotFoundError:
    raise SystemExit('error: clang not found')
if not a.keep_llvm: ll.unlink(missing_ok=True)
print(out)
