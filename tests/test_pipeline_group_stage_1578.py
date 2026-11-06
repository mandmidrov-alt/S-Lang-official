from pathlib import Path
from slang.core import parse, validate, native_csv_group_aggregate_llvm_ir
from slang.execution_ir import build_execution_ir
from slang.pipeline_ir import build_pipeline_ir


def test_group_count_is_canonical_group_stage(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,role\nA,engineer\nA,designer\nB,engineer\n", encoding="utf-8")
    module = parse(f'''let rows = read_csv("{csv.as_posix()}")
selected = rows where item.role == "engineer"
let result = group_count(selected, "team")
show result
''')
    ir = build_execution_ir(module.ast)
    pipeline = build_pipeline_ir(ir, "result")
    assert pipeline.kinds == ("filter", "group")
    assert pipeline.source == "rows"
    llvm = native_csv_group_aggregate_llvm_ir(module)
    assert "slang_csv_group_count_where_text_print" in llvm
