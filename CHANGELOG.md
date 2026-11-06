## 1.0 — Numeric integer validation consistency

- Made integer-valued numeric checks accept Python `int` and integral `float` values consistently.
- Explicitly reject booleans, non-numeric values, fractional values, infinities, and NaN.
- Updated parity predicates, GCD, LCM, and factorial validation to use the shared safe predicate.
- Added regression tests for integer/float interoperability and invalid numeric values.


## 1.0 — Windows native runtime DLL exports

- Exported the public `slang_*` C ABI from the Windows native runtime DLL using `__declspec(dllexport)`.
- Kept the export annotation empty on Linux and macOS, preserving their existing ABI and build behavior.
- Synchronized `slang/slang_runtime.c` and `runtime/slang_runtime.c`.
- Added regression coverage for the CSV ABI symbols required by frozen Windows Native JIT execution.

# S-Lang 1.0 — Stable Release

S-Lang 1.0 consolidates the language implementation, compiler/runtime, standard library, editor integrations, documentation, and release tooling into the first public 1.0 release line.

## Language and compiler

- Deterministic, documented grammar with explicit syntax boundaries.
- Explicit bindings (`let`) and mutable state (`state` / `set`).
- Functions, generic functions, records, entities, properties, and typed declarations.
- Declarative collection operations, reduction, and single-line pipelines.
- Modules, imports, exports, and transitive re-export behavior.
- Domain-oriented constructs for data tables, sequences, constraints, graphs, physical quantities, and simulations.
- Static semantic and type validation with structured diagnostics.

## Runtime and backends

- Interpreter execution.
- In-process LLVM Native JIT for supported programs.
- Native runtime ABI and bundled C runtime support.
- Explicit backend capability checks and diagnostics for unsupported execution shapes.
- Self-contained frozen runtime packaging for Windows, Linux, and macOS build targets.

## Standard library

- 13 public modules and 277 catalogued public function entries.
- Mathematics, text, collections, data access, aggregation, relational operations, analytics, CSV, JSON, files, paths, processes, and date/time functionality.
- Semantic signatures and validation for public library operations.

## Editor support

- Visual Studio Code, Zed, Neovim, and Emacs integrations.
- Shared Language Server Protocol implementation.
- Syntax highlighting, diagnostics, project commands, and editor workflows.

## Documentation and release packaging

- English LaTeX user guide and normative language reference.
- English design principles and release README.
- Windows runtime executable name: `slang1.0.exe`.
- Windows installer and cross-platform release workflows.

## Compatibility notes

S-Lang 1.0 intentionally does not adopt syntax merely because it is familiar from another language. In particular, `for` and `while` statements, lambda expressions, list indexing, and multi-line pipelines are not part of the documented grammar. Consult the normative syntax reference before relying on a construct.
