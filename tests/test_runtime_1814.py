from slang.ast import Module
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.core import parse
from slang.runtime import execute


def test_unified_runtime_does_not_depend_on_core_run(monkeypatch):
    module = parse("""
function double(x: Number) -> Number:
    return x * 2

value = double(21)
""")

    import slang.core as core
    original = core.run
    monkeypatch.setattr(core, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("reference run used")))
    module, trace = execute(module)
    assert module._bindings["value"] == 42
    assert trace.executor == "plan-runtime-segmented"
    monkeypatch.setattr(core, "run", original)


def test_reference_runtime_is_explicit_fallback(monkeypatch):
    import slang.core as core
    import slang.reference_runtime as rr

    module = object()
    called = []
    monkeypatch.setattr(core, "run", lambda m: called.append(m))
    assert rr.execute(module) is None
    assert called == [module]


def test_plan_runtime_has_no_direct_core_runtime_import():
    from pathlib import Path
    source = Path("slang/runtime.py").read_text()
    assert "from .core import" not in source
    assert "import slang.core" not in source
