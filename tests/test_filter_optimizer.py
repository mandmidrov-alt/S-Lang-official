from slang.core import parse, validate, run
from slang.optimizer import optimize_program


def test_filter_fusion_preserves_result_and_removes_intermediate():
    src = '''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\n    Carol age 31 score 95\n    Dave age 25 score 72\n\nadults = people where age >= 18\nelite = adults where score >= 90\nshow elite\n'''
    p = parse(src); validate(p)
    report = optimize_program(p)
    assert report.filter_fusions == 1
    assert len(p.ast.filters) == 1
    run(p)
    assert [r['name'] for r in p._collections['elite']] == ['Alice', 'Carol']


def test_observable_intermediate_blocks_filter_fusion():
    src = '''data people:\n    Alice age 22 score 91\n    Bob age 17 score 88\n\nadults = people where age >= 18\nelite = adults where score >= 90\nshow adults, elite\n'''
    p = parse(src); validate(p)
    report = optimize_program(p)
    assert report.filter_fusions == 0
