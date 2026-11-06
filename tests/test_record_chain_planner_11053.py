from slang.core import parse, validate
from slang.optimizer import optimize_program


def _source(count=8):
    records = []
    for i in range(count + 1):
        records.append(f"record R{i}:\n    value: Number\n")
    lines = records + ['let people = [R0(1), R0(2), R0(3)]']
    for i in range(count):
        lines.append(f"r{i+1} = r{i} map R{i+1}(row.value + {i+1})" if i else "r1 = people map R1(row.value + 1)")
    lines.append(f"show r{count}")
    return '\n'.join(lines)


def test_long_record_chain_gets_global_partial_plan():
    p = parse(_source(8))
    validate(p)
    report = optimize_program(p)
    decisions = getattr(p, '_record_fusion_decisions', [])
    assert decisions
    decision = decisions[0]
    assert decision.mode == 'partial'
    assert len(decision.fused_segments) >= 2
    assert report.record_transform_partial == 1


def test_short_record_chain_prefers_full_fusion():
    p = parse(_source(3))
    validate(p)
    report = optimize_program(p)
    decision = getattr(p, '_record_fusion_decisions', [])[0]
    assert decision.mode == 'full'
    assert len(decision.fused_segments) == 1
    assert report.record_transform_partial == 0
