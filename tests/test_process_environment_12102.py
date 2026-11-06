import os

import pytest

from slang.stdlib import environment, has_environment, set_environment, remove_environment
from slang.stdlib.registry import get


def test_environment_presence_and_mutation_isolated():
    name = "SLANG_TEST_ENV_12102"
    os.environ.pop(name, None)
    assert not has_environment(name)
    assert environment(name) == ""
    assert set_environment(name, "value-α") is True
    assert has_environment(name)
    assert environment(name) == "value-α"
    assert remove_environment(name) is True
    assert not has_environment(name)
    assert remove_environment(name) is False


def test_environment_validation():
    with pytest.raises(ValueError):
        has_environment("")
    with pytest.raises(ValueError):
        set_environment("", "x")
    with pytest.raises(ValueError):
        remove_environment("")
    with pytest.raises(TypeError):
        has_environment(123)
    with pytest.raises(TypeError):
        set_environment("x", 123)
    with pytest.raises(TypeError):
        remove_environment(123)


def test_environment_registry_contracts():
    assert get("has_environment").effect == "IO"
    assert get("set_environment").effect == "IO"
    assert get("remove_environment").effect == "IO"
