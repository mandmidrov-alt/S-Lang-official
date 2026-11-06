from slang.memory_regions import MemoryRegion

def test_structured_collection_region_parsing():
    r = MemoryRegion.parse('people[*].score')
    assert r.root == 'people'
    assert r.selector == '*'
    assert r.path == ('score',)
    assert r.scope == 'field'
    assert r.canonical == 'people[*].score'

def test_disjoint_fields_do_not_overlap():
    assert not MemoryRegion.parse('people[*].age').overlaps(MemoryRegion.parse('people[*].score'))

def test_whole_collection_overlaps_field():
    assert MemoryRegion.parse('people[*]').overlaps(MemoryRegion.parse('people[*].score'))

def test_different_roots_do_not_overlap():
    assert not MemoryRegion.parse('people[*].age').overlaps(MemoryRegion.parse('orders[*].total'))
