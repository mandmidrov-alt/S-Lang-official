from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline


def test_pipeline_ir_orders_cross_bucket_stages(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nA,10\nA,20\nB,30\n", encoding="utf-8")
    source = f'''let rows = read_csv("{csv.as_posix()}")
result = rows |> where item.team == "A" |> map to_number(item.score) |> sum item
show result
'''
    pipeline = compile_semantic_pipeline(parse(source).ast)
    assert pipeline.pipeline_ir is not None
    assert pipeline.pipeline_ir.terminal == "result"
    assert pipeline.pipeline_ir.kinds == ("filter", "map", "aggregate")
    assert pipeline.pipeline_ir.stages[0].source == "rows"


def test_pipeline_ir_is_deterministic(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nA,10\n", encoding="utf-8")
    source = f'''let rows = read_csv("{csv.as_posix()}")
result = rows |> where item.team == "A" |> map to_number(item.score) |> sum item
show result
'''
    ast = parse(source).ast
    a = compile_semantic_pipeline(ast).pipeline_ir
    b = compile_semantic_pipeline(ast).pipeline_ir
    assert a == b


def test_pipeline_ir_preserves_sort_stage(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nA,10\nB,20\n", encoding="utf-8")
    source = f'''let rows = read_csv("{csv.as_posix()}")
result = rows |> where item.team == "A" |> sort by row.score asc |> map to_number(item.score) |> sum item
show result
'''
    pipeline = compile_semantic_pipeline(parse(source).ast).pipeline_ir
    assert pipeline is not None
    assert pipeline.kinds == ("filter", "sort", "map", "aggregate")
