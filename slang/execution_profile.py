"""Concrete execution context used by S-Lang strategy selection."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ExecutionProfile:
    """Deterministic description of the environment available to a plan.

    Values are compile-time inputs, not runtime measurements.  Unknown values
    remain conservative so the profile cannot silently change semantics.
    """
    memory_budget: float | None = None
    cpu_cores: int = 1
    allow_parallelism: bool = False
    materialization_cost: float = 1.0
    memory_cost: float = 1.0

    def __post_init__(self):
        if self.memory_budget is not None and self.memory_budget <= 0:
            raise ValueError("memory_budget must be positive when provided")
        if self.cpu_cores < 1:
            raise ValueError("cpu_cores must be at least 1")
        if self.materialization_cost < 0 or self.memory_cost < 0:
            raise ValueError("profile costs must be non-negative")

    @classmethod
    def reference(cls) -> "ExecutionProfile":
        return cls()

    def preferences(self) -> tuple[tuple[str, float], ...]:
        """Translate environment pressure into deterministic cost weights."""
        parallel_weight = 0.0 if not self.allow_parallelism or self.cpu_cores <= 1 else 0.5
        return (
            ("cpu_cores", float(self.cpu_cores)),
            ("memory", float(self.memory_cost)),
            ("materialization", float(self.materialization_cost)),
            ("parallelism", parallel_weight),
        )


def format_execution_profile(profile: ExecutionProfile) -> str:
    budget = "unknown" if profile.memory_budget is None else f"{profile.memory_budget:g}"
    return (
        "execution.profile {\n"
        f"  memory_budget = {budget}\n"
        f"  cpu_cores = {profile.cpu_cores}\n"
        f"  allow_parallelism = {'yes' if profile.allow_parallelism else 'no'}\n"
        f"  materialization_cost = {profile.materialization_cost:g}\n"
        f"  memory_cost = {profile.memory_cost:g}\n"
        "  deterministic = yes\n"
        "}"
    )
