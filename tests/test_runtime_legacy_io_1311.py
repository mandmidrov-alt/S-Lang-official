import os
import sys

import pytest

from slang.stdlib_runtime import RuntimeCapabilityError, capture_runtime_trace, runtime_effect_policy
from slang.stdlib.process import current_directory, platform_name
from slang.plan_expression import eval_expr as plan_eval
from slang.reference_expression import eval_expr as reference_eval
from slang.ast import Call, Literal


class DummyPlan:
    _bindings = {}
    _plan_functions = {}
    _states = {}
    bodies = []
    circles = []


class DummyAst:
    entities = []
    records = []
    functions = []


class DummyReference(DummyPlan):
    ast = DummyAst()


def test_plan_legacy_process_calls_are_blocked_before_execution():
    with runtime_effect_policy(allowed_effects={"pure"}, allowed_capabilities={"pure"}):
        with pytest.raises(RuntimeCapabilityError):
            plan_eval(Call("environment", [Literal("PATH")]), DummyPlan())


def test_reference_legacy_process_calls_are_blocked_before_execution():
    with runtime_effect_policy(allowed_effects={"pure"}, allowed_capabilities={"pure"}):
        with pytest.raises(RuntimeCapabilityError):
            reference_eval(Call("current_directory", []), DummyReference())


def test_legacy_process_calls_share_runtime_trace():
    with capture_runtime_trace() as events:
        result = plan_eval(Call("platform_name", []), DummyPlan())
    assert result == platform_name()
    assert events[-1].name == "platform_name"
    assert events[-1].effect == "IO"
    assert events[-1].success is True
