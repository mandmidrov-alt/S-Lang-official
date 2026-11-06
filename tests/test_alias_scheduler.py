from slang.execution_ir import ExecutionIR, ExecutionNode
from slang.execution_scheduler import build_schedule
from slang.memory_regions import MemoryRegion

def node(name, region, access="write"):
    return ExecutionNode(
        binding=name, kind="test", result=name, dependencies=(), external_sources=(),
        pure=False, access=access, memory_regions=(region.canonical,),
        memory_region_specs=(region,), memory_writes=(region.canonical,) if access == "write" else (),
    )

def batch_map(schedule):
    return {name:i for i,batch in enumerate(schedule.batches) for name in batch}

def test_scheduler_uses_no_alias_for_disjoint_written_regions():
    a=node("a", MemoryRegion.parse("people[*].age"))
    b=node("b", MemoryRegion.parse("people[*].score"))
    pos=batch_map(build_schedule(ExecutionIR((a,b))))
    assert pos["a"] == pos["b"]

def test_scheduler_orders_may_alias_written_regions():
    a=node("a", MemoryRegion.parse("people[*]"))
    b=node("b", MemoryRegion.parse("people[*].score"))
    pos=batch_map(build_schedule(ExecutionIR((a,b))))
    assert pos["a"] != pos["b"]
