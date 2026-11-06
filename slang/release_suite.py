"""S-Lang 1.0 release-candidate semantic acceptance suite."""
from __future__ import annotations
from .validation_suite import run_suite as validation_suite
from .practical_suite import run_suite as practical_suite
from .goal_directed_suite import run_suite as goal_suite
from .stress_suite import run_suite as stress_suite
from .stability_suite import run_suite as stability_suite
from .parallel_determinism_suite import run_suite as parallel_determinism_suite
from .compiler_artifact import CompilerArtifact
from .compiler_pipeline import compile_semantic_pipeline, compiler_artifact
from .core import parse
from .stdlib.catalog import entries as stdlib_entries
from .stdlib_runtime import validate_runtime_contracts


def run_suite() -> dict[str, object]:
    validation = validation_suite()
    practical = practical_suite()
    goals = goal_suite()
    stress = stress_suite()
    stability = stability_suite()
    parallel_determinism = parallel_determinism_suite()

    artifact_source = parse("""data people:
    Alice age 20
    Bob age 16
adults = people where age >= 18
show adults
""")
    artifact = compiler_artifact(compile_semantic_pipeline(artifact_source.ast))
    restored_artifact = CompilerArtifact.from_json(artifact.to_json())
    artifact_contract = (
        bool(artifact.fingerprint)
        and restored_artifact.fingerprint == artifact.fingerprint
        and restored_artifact.artifact_version == artifact.artifact_version
    )

    stdlib_contract_errors = validate_runtime_contracts()
    stdlib_surface = stdlib_entries()
    stdlib_contract = bool(stdlib_surface) and not stdlib_contract_errors

    checks = {
        "validation": all(row["semantic_match"] for row in validation),
        "practical": all(row.get("semantic_match", True) for row in practical),
        "goals": all(row.get("semantic_match", True) for row in goals),
        "stress": all(row.get("semantic_match", True) for row in stress),
        "stability": all(row["stable"] for row in stability),
        "parallel_determinism": all(row["stable"] for row in parallel_determinism),
        "compiler_artifact_contract": artifact_contract,
        "stdlib_contract": stdlib_contract,
    }
    return {
        "checks": checks,
        "release_ready": all(checks.values()),
        "counts": {
            "validation": len(validation),
            "practical": len(practical),
            "goals": len(goals),
            "stress": len(stress),
            "stability": len(stability),
            "parallel_determinism": len(parallel_determinism),
            "stdlib_entries": len(stdlib_surface),
            "stdlib_contract_errors": list(stdlib_contract_errors),
            "compiler_artifact_version": artifact.artifact_version,
            "compiler_artifact_fingerprint": artifact.fingerprint,
        },
    }
