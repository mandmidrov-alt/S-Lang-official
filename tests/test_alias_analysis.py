from slang.memory_regions import MemoryRegion
from slang.alias_analysis import classify


def test_identical_regions_must_alias():
    a = MemoryRegion.parse("people[*].age")
    b = MemoryRegion.parse("people[*].age")
    assert classify(a, b)[0] == "must-alias"


def test_different_roots_do_not_alias():
    a = MemoryRegion.parse("people[*].age")
    b = MemoryRegion.parse("orders[*].total")
    assert classify(a, b)[0] == "no-alias"


def test_parent_child_is_may_alias():
    a = MemoryRegion.parse("people[*]")
    b = MemoryRegion.parse("people[*].age")
    assert classify(a, b)[0] == "may-alias"
