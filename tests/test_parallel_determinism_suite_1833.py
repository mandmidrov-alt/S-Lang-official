from slang.parallel_determinism_suite import run_suite


def test_parallel_determinism_acceptance_suite():
    result = run_suite()
    assert all(row["stable"] for row in result)
