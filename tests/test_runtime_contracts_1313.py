from slang.stdlib_runtime import validate_runtime_contracts, validate_runtime_boundary_coverage

def test_runtime_contracts_are_complete():
    assert validate_runtime_contracts() == ()


def test_runtime_boundary_covers_catalog_io_in_both_evaluators():
    assert validate_runtime_boundary_coverage() == ()
