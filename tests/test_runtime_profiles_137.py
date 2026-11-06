from slang.stdlib_runtime import runtime_execution_profile, RuntimeCapabilityError, execute_registered_stdlib


def test_restricted_profile_denies_environment_capability():
    with runtime_execution_profile("restricted"):
        try:
            execute_registered_stdlib("environment", ["PATH"])
            assert False, "expected RuntimeCapabilityError"
        except RuntimeCapabilityError:
            pass


def test_normal_profile_preserves_legacy_behavior():
    with runtime_execution_profile("normal"):
        ok, value = execute_registered_stdlib("sqrt", [49])
        assert ok and value == 7
