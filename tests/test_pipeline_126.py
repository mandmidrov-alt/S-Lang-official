from pathlib import Path
import pytest
from slang.core import parse_file, validate, run, ParseError

ROOT = Path(__file__).resolve().parents[1]

def execute(name):
    p = parse_file(ROOT / "examples" / name)
    validate(p)
    run(p)
    return p

def test_pipeline_tee_creates_reusable_branch():
    p = execute("pipeline_tee.sl")
    assert p._collections["adults"] == [
        {"name": "Ada", "age": 36, "score": 96},
        {"name": "Cara", "age": 52, "score": 94},
        {"name": "Dan", "age": 44, "score": 91},
    ]
    assert p._collections["result"] == [96, 94, 91]
    assert p._collections["older"] == [94]

def test_pipeline_tee_must_continue():
    path = ROOT / "examples" / "_bad_tee.sl"
    path.write_text("data people:\n    Ada age 36\n\nresult = people |> tee adults\n", encoding="utf-8")
    try:
        with pytest.raises(ParseError, match="tee.*followed"):
            parse_file(path)
    finally:
        path.unlink(missing_ok=True)

def test_pipeline_tee_target_must_differ():
    path = ROOT / "examples" / "_bad_tee2.sl"
    path.write_text("data people:\n    Ada age 36\n\nresult = people |> tee people |> map row.age\n", encoding="utf-8")
    try:
        with pytest.raises(ParseError, match="target must differ"):
            parse_file(path)
    finally:
        path.unlink(missing_ok=True)
