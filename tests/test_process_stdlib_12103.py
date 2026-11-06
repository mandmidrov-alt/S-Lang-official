import os
import sys

from slang.stdlib import argument_count, argument_at, environment_or
from slang.stdlib.registry import REGISTRY
from slang.stdlib.catalog import entries

def test_environment_or():
    key="SLANG_TEST_12103"
    os.environ.pop(key, None)
    assert environment_or(key, "fallback") == "fallback"
    os.environ[key]="value"
    assert environment_or(key, "fallback") == "value"
    del os.environ[key]

def test_argument_access():
    old=list(sys.argv)
    try:
        sys.argv=["slang", "one", "two"]
        assert argument_count() == 2
        assert argument_at(0) == "one"
        assert argument_at(1) == "two"
    finally:
        sys.argv[:] = old

def test_argument_bounds():
    old=list(sys.argv)
    try:
        sys.argv=["slang"]
        try:
            argument_at(0)
            assert False
        except IndexError:
            pass
    finally:
        sys.argv[:] = old

def test_public_registration():
    assert REGISTRY["argument_count"].effect == "IO"
    assert REGISTRY["argument_at"].effect == "IO"
    assert REGISTRY["environment_or"].effect == "IO"
    names={e["name"] for e in entries()}
    assert {"argument_count","argument_at","environment_or"} <= names
