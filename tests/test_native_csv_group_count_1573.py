from pathlib import Path
import subprocess
import sys

from slang.core import parse, run, show_expr_value, validate


def test_native_csv_group_count_matches_reference(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nA,10\nB,5\nA,20\nB,15\nA,30\n", encoding="utf-8")
    source = tmp_path / "group.sl"
    source.write_text(f'''let rows = read_csv("{csv.as_posix()}")\nlet result = group_count(rows, "team")\nshow result\n''', encoding="utf-8")

    p = parse(source.read_text(encoding="utf-8"))
    validate(p)
    run(p)
    expected = show_expr_value(p, p.show_exprs[0])
    assert expected == "[row(key=A, count=3), row(key=B, count=2)]"

    out = tmp_path / "native"
    cmd = [sys.executable, "-m", "slang.cli", "run", str(source), "--native"]
    result = subprocess.run(cmd, cwd=Path(__file__).parents[1], text=True, capture_output=True, check=True)
    assert result.stdout.strip() == expected


def test_native_csv_group_sum_is_not_selected_for_text_csv(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nA,10\n", encoding="utf-8")
    source = tmp_path / "group_sum.sl"
    source.write_text(f'''let rows = read_csv("{csv.as_posix()}")\nlet result = group_sum(rows, "team", "score")\nshow result\n''', encoding="utf-8")
    # Reference semantics intentionally reject CSV text fields as Number.
    p = parse(source.read_text(encoding="utf-8"))
    validate(p)
    try:
        run(p)
    except TypeError as exc:
        assert "group_sum value field must contain Number values" in str(exc)
    else:
        raise AssertionError("reference group_sum unexpectedly accepted CSV Text values")
