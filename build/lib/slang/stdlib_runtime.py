"""Common runtime boundary for registered S-Lang standard-library calls.

This module is shared by the plan and reference expression evaluators. It keeps
argument-count validation, runtime error normalization, and optional execution
tracing identical across both execution paths.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator, Iterable
from collections import Counter

from .plan_runtime_support import get_stdlib_function
from .stdlib.registry import build_registry


@dataclass(frozen=True)
class RuntimeEffectPolicy:
    """Runtime permission policy for registered standard-library calls."""

    allowed_effects: frozenset[str] | None = None
    allowed_capabilities: frozenset[str] | None = None

    def allows(self, effect: str, capability: str) -> bool:
        effect_ok = self.allowed_effects is None or effect in self.allowed_effects
        capability_ok = self.allowed_capabilities is None or capability in self.allowed_capabilities
        return effect_ok and capability_ok


class RuntimeCapabilityError(RuntimeError):
    """Raised when a runtime call requires a capability not granted by policy."""


# Capabilities are declared by each registered stdlib function.
# The runtime reads that metadata directly so registry and permission policy
# cannot silently diverge.
def validate_runtime_contracts() -> tuple[str, ...]:
    """Validate effect/capability metadata for the complete stdlib surface.

    The runtime treats this metadata as an executable permission contract.
    A missing capability or an invalid effect/capability pairing is therefore
    a release-time error rather than something discovered during a restricted run.
    """
    from .stdlib.catalog import IO_LIBRARY

    errors: list[str] = []
    registry = build_registry()
    for name, fn in registry.items():
        if not fn.capability:
            errors.append(f"{name}: missing capability")
        if not fn.effect:
            errors.append(f"{name}: missing effect")
        if fn.effect == "pure" and fn.capability != "pure":
            errors.append(f"{name}: pure function must declare pure capability")
    for name, entry in IO_LIBRARY.items():
        if len(entry) != 4:
            errors.append(f"{name}: invalid catalog metadata")
            continue
        _module, effect, _description, capability = entry
        if not effect or not capability:
            errors.append(f"{name}: missing effect/capability")
        if effect == "pure" and capability != "pure":
            errors.append(f"{name}: pure catalog entry must declare pure capability")
        if effect != "pure" and capability == "pure":
            errors.append(f"{name}: effectful catalog entry cannot declare pure capability")
    return tuple(errors)


def registered_stdlib_capability(name: str) -> str:
    """Return the capability declared by a registered stdlib call."""
    fn = get_stdlib_function(name)
    if fn is not None:
        return fn.capability
    from .stdlib.catalog import capability_for
    capability = capability_for(name)
    return "pure" if capability is None else capability


_POLICY: ContextVar[RuntimeEffectPolicy | None] = ContextVar(
    "slang_runtime_effect_policy", default=None
)


def _normalize_policy_values(values: Iterable[str] | None, label: str) -> frozenset[str] | None:
    if values is None:
        return None
    normalized = frozenset(values)
    if not all(isinstance(value, str) and value for value in normalized):
        raise TypeError(f"{label} must contain non-empty text values")
    return normalized


@contextmanager
def runtime_effect_policy(
    allowed_effects: Iterable[str] | None = None,
    allowed_capabilities: Iterable[str] | None = None,
) -> Iterator[RuntimeEffectPolicy]:
    """Temporarily restrict registered stdlib execution by effect/capability."""
    policy = RuntimeEffectPolicy(
        allowed_effects=_normalize_policy_values(allowed_effects, "allowed_effects"),
        allowed_capabilities=_normalize_policy_values(allowed_capabilities, "allowed_capabilities"),
    )
    token = _POLICY.set(policy)
    try:
        yield policy
    finally:
        _POLICY.reset(token)


@dataclass(frozen=True)
class RuntimeExecutionProfile:
    """Named runtime permission profile."""

    name: str
    policy: RuntimeEffectPolicy


def _profile(name: str) -> RuntimeExecutionProfile:
    if name == "normal":
        return RuntimeExecutionProfile(name, RuntimeEffectPolicy())
    if name in {"safe", "restricted"}:
        pure = frozenset({"pure"})
        # Safe/restricted profiles deliberately deny host effects.
        return RuntimeExecutionProfile(name, RuntimeEffectPolicy(allowed_effects=pure, allowed_capabilities=pure))
    raise ValueError("unknown runtime execution profile: " + name)


@contextmanager
def runtime_execution_profile(name: str = "normal") -> Iterator[RuntimeExecutionProfile]:
    """Apply a named runtime permission profile for the current execution context."""
    profile = _profile(name)
    token = _POLICY.set(profile.policy)
    try:
        yield profile
    finally:
        _POLICY.reset(token)


def current_runtime_effect_policy() -> RuntimeEffectPolicy | None:
    """Return the currently active runtime permission policy, if any."""
    return _POLICY.get()


def _check_runtime_policy(name: str, effect: str) -> None:
    policy = _POLICY.get()
    if policy is None:
        return
    capability = registered_stdlib_capability(name)
    if not policy.allows(effect, capability):
        raise RuntimeCapabilityError(
            f"runtime permission denied for {name}: effect={effect}, capability={capability}"
        )


@dataclass(frozen=True)
class RuntimeTraceEvent:
    """One registered-stdlib execution observed at the runtime boundary."""

    name: str
    effect: str
    argument_count: int
    success: bool
    duration_ms: float
    error_type: str | None = None


_TRACE_SINKS: ContextVar[tuple[list[RuntimeTraceEvent], ...]] = ContextVar(
    "slang_runtime_trace_sinks", default=()
)


@dataclass(frozen=True)
class RuntimeExecutionSummary:
    """Aggregate facts about registered stdlib calls in one execution."""

    event_count: int
    successful_count: int
    failed_count: int
    effects: tuple[str, ...]
    calls_by_name: tuple[tuple[str, int], ...]


class RuntimeLimitError(RuntimeError):
    """Raised when an execution context exceeds a configured runtime limit."""


@dataclass(frozen=True)
class RuntimeExecutionLimits:
    """Optional limits enforced at the common registered-stdlib runtime boundary."""

    max_events: int | None = None
    max_duration_ms: float | None = None


_LIMITS: ContextVar[RuntimeExecutionLimits | None] = ContextVar(
    "slang_runtime_execution_limits", default=None
)
_EXECUTION_STARTED: ContextVar[float | None] = ContextVar(
    "slang_runtime_execution_started", default=None
)
_EVENT_COUNT: ContextVar[int] = ContextVar("slang_runtime_event_count", default=0)


@dataclass
class RuntimeExecutionContext:
    """Unified state for one complete S-Lang runtime execution."""

    limits: RuntimeExecutionLimits
    events: list[RuntimeTraceEvent]
    started_at: float

    @property
    def elapsed_ms(self) -> float:
        return (perf_counter() - self.started_at) * 1000.0

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def summary(self) -> RuntimeExecutionSummary:
        return summarize_runtime_trace(self.events)

    @property
    def effects(self) -> tuple[str, ...]:
        return self.summary.effects

    def reset_events(self) -> None:
        self.events.clear()


def _validate_limits(max_events: int | None, max_duration_ms: float | None) -> RuntimeExecutionLimits:
    if max_events is not None and (isinstance(max_events, bool) or max_events < 0):
        raise ValueError("max_events must be a non-negative integer or None")
    if max_events is not None and not isinstance(max_events, int):
        raise TypeError("max_events must be an integer or None")
    if max_duration_ms is not None and (isinstance(max_duration_ms, bool) or not isinstance(max_duration_ms, (int, float))):
        raise TypeError("max_duration_ms must be a number or None")
    if max_duration_ms is not None and max_duration_ms < 0:
        raise ValueError("max_duration_ms must be non-negative")
    return RuntimeExecutionLimits(
        max_events=max_events,
        max_duration_ms=float(max_duration_ms) if max_duration_ms is not None else None,
    )


@contextmanager
def runtime_limits(
    max_events: int | None = None,
    max_duration_ms: float | None = None,
) -> Iterator[RuntimeExecutionLimits]:
    """Apply execution limits to registered stdlib calls in the current context."""
    limits = _validate_limits(max_events, max_duration_ms)
    token_limits = _LIMITS.set(limits)
    token_started = _EXECUTION_STARTED.set(perf_counter())
    token_count = _EVENT_COUNT.set(0)
    try:
        yield limits
    finally:
        _EVENT_COUNT.reset(token_count)
        _EXECUTION_STARTED.reset(token_started)
        _LIMITS.reset(token_limits)


def _check_execution_limits(*, check_event_count: bool = True) -> None:
    limits = _LIMITS.get()
    if limits is None:
        return
    if check_event_count and limits.max_events is not None and _EVENT_COUNT.get() >= limits.max_events:
        raise RuntimeLimitError(
            f"runtime event limit exceeded: maximum {limits.max_events} event(s)"
        )
    if limits.max_duration_ms is not None:
        started = _EXECUTION_STARTED.get()
        if started is not None and (perf_counter() - started) * 1000.0 >= limits.max_duration_ms:
            raise RuntimeLimitError(
                f"runtime duration limit exceeded: maximum {limits.max_duration_ms:g} ms"
            )


def summarize_runtime_trace(events: list[RuntimeTraceEvent]) -> RuntimeExecutionSummary:
    """Create a deterministic summary from captured runtime trace events."""
    names = Counter(event.name for event in events)
    effects = tuple(sorted({event.effect for event in events}))
    calls = tuple(sorted(names.items()))
    successful = sum(1 for event in events if event.success)
    return RuntimeExecutionSummary(
        event_count=len(events),
        successful_count=successful,
        failed_count=len(events) - successful,
        effects=effects,
        calls_by_name=calls,
    )


@contextmanager
def runtime_execution_context(
    max_events: int | None = None,
    max_duration_ms: float | None = None,
) -> Iterator[RuntimeExecutionContext]:
    """Establish one unified state object for a complete program execution."""
    limits = _validate_limits(max_events, max_duration_ms)
    context = RuntimeExecutionContext(
        limits=limits,
        events=[],
        started_at=perf_counter(),
    )
    token_sinks = _TRACE_SINKS.set((context.events,))
    token_limits = _LIMITS.set(limits)
    token_started = _EXECUTION_STARTED.set(context.started_at)
    token_count = _EVENT_COUNT.set(0)
    try:
        yield context
    finally:
        _EVENT_COUNT.reset(token_count)
        _EXECUTION_STARTED.reset(token_started)
        _LIMITS.reset(token_limits)
        _TRACE_SINKS.reset(token_sinks)


@contextmanager
def capture_runtime_trace() -> Iterator[list[RuntimeTraceEvent]]:
    """Capture registered standard-library calls made in the current context."""
    events: list[RuntimeTraceEvent] = []
    token = _TRACE_SINKS.set(_TRACE_SINKS.get() + (events,))
    try:
        yield events
    finally:
        _TRACE_SINKS.reset(token)


def _record_trace(event: RuntimeTraceEvent) -> None:
    for sink in _TRACE_SINKS.get():
        sink.append(event)


def execute_registered_stdlib(name: str, args: list[object]):
    """Execute a registered standard-library function through the runtime boundary."""
    _check_execution_limits()
    fn = get_stdlib_function(name)
    if fn is None:
        return False, None
    started = perf_counter()
    # Reserve the event before invoking the evaluator. Nested standard-library
    # calls must see the outer call in the shared budget immediately.
    _EVENT_COUNT.set(_EVENT_COUNT.get() + 1)
    if len(args) != len(fn.parameters):
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=fn.effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type="TypeError",
        ))
        raise TypeError(f"{name} expects {len(fn.parameters)} argument(s), got {len(args)}")

    try:
        _check_runtime_policy(name, fn.effect)
        result = fn.evaluator(args)
        # Check again after the operation so a single long-running call cannot
        # silently succeed beyond the configured duration budget.
        _check_execution_limits(check_event_count=False)
    except (RuntimeCapabilityError, RuntimeLimitError) as exc:
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=fn.effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type=type(exc).__name__,
        ))
        raise
    except (OSError, TypeError, ValueError, OverflowError) as exc:
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=fn.effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type=type(exc).__name__,
        ))
        if name == "json_parse" and isinstance(exc, ValueError):
            message = (
                f"json_parse could not read valid JSON: {exc}. "
                "Check quotes, commas, brackets, and the value at the reported position."
            )
        else:
            message = f"{name} failed: {exc}"
        raise RuntimeError(message) from exc
    except Exception as exc:
        # Unexpected evaluator failures must consume one event just like
        # validation, policy, and known runtime failures.
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=fn.effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type=type(exc).__name__,
        ))
        raise
    except BaseException as exc:
        # Cancellation and process-control exceptions must never be wrapped or
        # swallowed, but recording them keeps tracing and event budgets honest.
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=fn.effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type=type(exc).__name__,
        ))
        raise

    _record_trace(RuntimeTraceEvent(
        name=name,
        effect=fn.effect,
        argument_count=len(args),
        success=True,
        duration_ms=(perf_counter() - started) * 1000.0,
    ))
    return True, result


def runtime_call_metadata(name: str) -> tuple[str, str] | None:
    """Return the declared ``(effect, capability)`` for any stdlib call.

    Registered functions are authoritative; legacy catalog entries use the
    same metadata contract until they are migrated into the executable
    registry.
    """
    fn = get_stdlib_function(name)
    if fn is not None:
        return fn.effect, fn.capability
    from .stdlib.catalog import IO_LIBRARY
    entry = IO_LIBRARY.get(name)
    if entry is None:
        return None
    return entry[1], entry[3]


def _filesystem_error_hint(name: str, args: list[object], exc: OSError) -> str:
    """Explain common filesystem failures without hiding the operating-system detail."""
    import errno

    path = str(args[0]) if args and isinstance(args[0], (str, bytes)) else None
    destination = str(args[1]) if len(args) > 1 and isinstance(args[1], (str, bytes)) else None
    detail = str(exc) or type(exc).__name__
    if exc.errno == errno.ENOENT:
        advice = "The path does not exist. Check its spelling and make sure the parent directory exists."
    elif exc.errno in (errno.EACCES, errno.EPERM):
        advice = "Access was denied. Check file permissions and whether another program is locking the file."
    elif exc.errno == errno.EISDIR:
        advice = "The path points to a directory, not a file. Choose a file path."
    elif exc.errno == errno.ENOTDIR:
        advice = "A path component is not a directory. Check each part of the path."
    elif exc.errno == errno.EEXIST:
        advice = "The path already exists. Choose a new name or use an operation that allows replacement."
    elif exc.errno == errno.ENOTEMPTY:
        advice = "The directory is not empty. Remove its contents first or use the tree-removal operation if intended."
    elif exc.errno == errno.ENOSPC:
        advice = "There is not enough free disk space. Free space and try again."
    elif exc.errno == errno.EROFS:
        advice = "The file system is read-only. Choose a writable location."
    else:
        advice = "Check that the path is valid and that the requested operation is permitted."
    location = f" for '{path}'" if path is not None else ""
    if name in {"copy_file", "move_file"} and destination is not None:
        location += f" to '{destination}'"
    return f"{name} failed{location}: {detail}. {advice}"


def execute_runtime_call(
    name: str,
    args: list[object],
    evaluator,
    *,
    expected_args: int | None = None,
    artifact=None,
    parameter_binding: str | None = None,
    parameter_seed: int | None = None,
    parameter_value_type: str | None = None,
    parameter_byte_size: int | None = None,
    parameter_operation_kind: str | None = None,
):
    """Run any stdlib call through the common permission/trace/limit boundary.

    This is the migration boundary for catalog-backed IO calls that have not
    yet moved into ``StdlibFunction``. The evaluator receives the already
    validated argument list.
    """
    _check_execution_limits()
    if artifact is not None or parameter_binding is not None or parameter_seed is not None:
        if artifact is None or parameter_binding is None or parameter_seed is None:
            raise ValueError("artifact, parameter_binding and parameter_seed must be provided together")
        from .runtime_parameter_abi import validate_runtime_call_parameter
        validate_runtime_call_parameter(
            artifact,
            parameter_binding,
            operation_kind=parameter_operation_kind or name,
            descriptor_seed=int(parameter_seed),
            value_type=parameter_value_type,
            byte_size=parameter_byte_size,
        )
    metadata = runtime_call_metadata(name)
    if metadata is None:
        return False, None
    effect, capability = metadata
    started = perf_counter()
    # Reserve before evaluation so nested calls consume the same event budget.
    _EVENT_COUNT.set(_EVENT_COUNT.get() + 1)
    if expected_args is not None and len(args) != expected_args:
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type="TypeError",
        ))
        raise TypeError(f"{name} expects {expected_args} argument(s), got {len(args)}")
    try:
        _check_runtime_policy(name, effect)
        result = evaluator(args)
        # Keep the catalog-backed compatibility boundary consistent with the
        # registered-function boundary for duration-budget enforcement.
        _check_execution_limits(check_event_count=False)
    except (RuntimeCapabilityError, RuntimeLimitError) as exc:
        _record_trace(RuntimeTraceEvent(name, effect, len(args), False, (perf_counter() - started) * 1000.0, type(exc).__name__))
        raise
    except OSError as exc:
        _record_trace(RuntimeTraceEvent(name, effect, len(args), False, (perf_counter() - started) * 1000.0, type(exc).__name__))
        raise RuntimeError(_filesystem_error_hint(name, args, exc)) from exc
    except UnicodeDecodeError as exc:
        _record_trace(RuntimeTraceEvent(name, effect, len(args), False, (perf_counter() - started) * 1000.0, type(exc).__name__))
        path = str(args[0]) if args and isinstance(args[0], (str, bytes)) else None
        location = f" for '{path}'" if path is not None else ""
        byte_offset = exc.start
        raise RuntimeError(
            f"{name} failed{location}: the file is not valid UTF-8 at byte offset {byte_offset}. "
            "Save the file as UTF-8 or convert it before reading; S-Lang text-file functions expect UTF-8."
        ) from exc
    except (TypeError, ValueError, OverflowError) as exc:
        _record_trace(RuntimeTraceEvent(name, effect, len(args), False, (perf_counter() - started) * 1000.0, type(exc).__name__))
        file_functions = {
            "read_text", "write_text", "append_text", "read_lines", "write_lines",
            "read", "write", "read_json", "write_json", "read_csv", "write_csv",
            "file_size", "is_file", "is_directory", "list_directory", "list_files",
            "list_directories", "make_directory", "remove_directory", "remove_directory_tree",
            "remove_file", "copy_file", "move_file", "make_directories", "exists",
        }
        if name in file_functions and isinstance(exc, TypeError):
            raise RuntimeError(
                f"{name} failed: expected a text file path as its path argument; "
                f"check the argument type. Details: {exc}"
            ) from exc
        raise RuntimeError(f"{name} failed: {exc}") from exc
    except Exception as exc:
        # Keep unexpected host/evaluator failures visible in traces and limits.
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type=type(exc).__name__,
        ))
        raise
    except BaseException as exc:
        # Propagate cancellation and process-control signals unchanged while
        # still making the interrupted call visible to trace consumers.
        _record_trace(RuntimeTraceEvent(
            name=name,
            effect=effect,
            argument_count=len(args),
            success=False,
            duration_ms=(perf_counter() - started) * 1000.0,
            error_type=type(exc).__name__,
        ))
        raise
    _record_trace(RuntimeTraceEvent(name, effect, len(args), True, (perf_counter() - started) * 1000.0))
    return True, result


def validate_runtime_boundary_coverage() -> tuple[str, ...]:
    """Validate that catalog-backed IO names are visible to both evaluators.

    This is a release-time structural guard: every catalog IO name must be
    represented in both expression evaluators, and both evaluators must use
    the shared runtime-call boundary. It does not execute host side effects.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent
    errors: list[str] = []
    from .stdlib.catalog import IO_LIBRARY
    for filename in ("plan_expression.py", "reference_expression.py"):
        source = (root / filename).read_text(encoding="utf-8")
        if "execute_runtime_call(" not in source:
            errors.append(f"{filename}: missing execute_runtime_call boundary")
        for name in IO_LIBRARY:
            if name not in source:
                errors.append(f"{filename}: missing catalog IO name {name}")
    return tuple(errors)


def registered_stdlib_effect(name: str) -> str | None:
    """Return the declared runtime effect for a registered function."""
    metadata = runtime_call_metadata(name)
    return None if metadata is None else metadata[0]

