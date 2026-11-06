from slang.stdlib.registry import get
from slang.stdlib_runtime import registered_stdlib_capability


def test_detailed_capability_mapping_is_deterministic():
    assert get("sqrt").capability == "pure"
    assert registered_stdlib_capability("sqrt") == "pure"
    assert registered_stdlib_capability("read_text") == "filesystem"
    assert registered_stdlib_capability("read_json") == "filesystem"
    assert registered_stdlib_capability("current_directory") == "filesystem"
    assert registered_stdlib_capability("run_program") == "process"
    assert registered_stdlib_capability("set_environment") == "environment"
    assert registered_stdlib_capability("platform_name") == "runtime"
