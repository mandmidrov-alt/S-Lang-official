from slang.core import parse, validate
from slang.runtime import execute
from slang.execution_profile import ExecutionProfile


def test_runtime_executes_specialized_filter_map_fusion():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
    d value 4
filtered = numbers where value >= 2
scaled = filtered map value * 2
total = scaled reduce 0 with acc + item
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-specialized"
    assert [step.strategy for step in trace.steps] == [
        "scan-filter", "sequential-map", "fused-filter-map-reduce"
    ]
    assert module._collections["total"] == 18
    assert "filtered" not in module._collections
    assert "scaled" not in module._collections


def test_runtime_executes_parallel_map_strategy():
    p = parse('''
data numbers:
    a value 1
    n1 value 1
    n2 value 2
    n3 value 3
    n4 value 4
    n5 value 5
    n6 value 6
    n7 value 7
    n8 value 8
    n9 value 9
    n10 value 10
    n11 value 11
    n12 value 12
    n13 value 13
    n14 value 14
    n15 value 15
    n16 value 16
    n17 value 17
    n18 value 18
    n19 value 19
    n20 value 20
    n21 value 21
    n22 value 22
    n23 value 23
    n24 value 24
    n25 value 25
    n26 value 26
    n27 value 27
    n28 value 28
    n29 value 29
    n30 value 30
    n31 value 31
    n32 value 32
    n33 value 33
    n34 value 34
    n35 value 35
    n36 value 36
    n37 value 37
    n38 value 38
    n39 value 39
    n40 value 40
    n41 value 41
    n42 value 42
    n43 value 43
    n44 value 44
    n45 value 45
    n46 value 46
    n47 value 47
    n48 value 48
    n49 value 49
    n50 value 50
    n51 value 51
    n52 value 52
    n53 value 53
    n54 value 54
    n55 value 55
    n56 value 56
    n57 value 57
    n58 value 58
    n59 value 59
    n60 value 60
    n61 value 61
    n62 value 62
    n63 value 63
    n64 value 64
    n65 value 65
    n66 value 66
    n67 value 67
    n68 value 68
    n69 value 69
    n70 value 70
    n71 value 71
    n72 value 72
    n73 value 73
    n74 value 74
    n75 value 75
    n76 value 76
    n77 value 77
    n78 value 78
    n79 value 79
    n80 value 80
    n81 value 81
    n82 value 82
    n83 value 83
    n84 value 84
    n85 value 85
    n86 value 86
    n87 value 87
    n88 value 88
    n89 value 89
    n90 value 90
    n91 value 91
    n92 value 92
    n93 value 93
    n94 value 94
    n95 value 95
    n96 value 96
    n97 value 97
    n98 value 98
    n99 value 99
    n100 value 100
scaled = numbers map value * 2
''')
    validate(p)
    module, trace = execute(p, ExecutionProfile(cpu_cores=4, allow_parallelism=True))
    assert trace.executor == "plan-runtime-specialized"
    assert any(step.strategy == "parallel-map" for step in trace.steps)
    assert module._collections["scaled"] == [2] + [i * 2 for i in range(1, 101)]


def test_runtime_specialized_aggregate_matches_reference_semantics():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
numbers_sum = numbers map value
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-specialized"
    assert module._collections["numbers_sum"] == [1, 2, 3]
