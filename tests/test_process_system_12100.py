import os
import sys

from slang.stdlib import current_directory, platform_name, process_id, sleep_seconds
from slang.stdlib.registry import get


def test_process_system_context():
    assert current_directory() == os.getcwd()
    assert platform_name() in {"windows", "macos", "linux", "freebsd", sys.platform}
    assert process_id() == float(os.getpid())
    assert sleep_seconds(0) is True


def test_process_system_registry_contracts():
    assert get("current_directory").effect == "IO"
    assert get("platform_name").effect == "IO"
    assert get("process_id").effect == "IO"
    assert get("sleep_seconds").effect == "IO"
