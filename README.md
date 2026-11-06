# S-Lang 1.0

S-Lang is a deterministic, high-level general-purpose programming language. It focuses on readable descriptions of tasks, data, and transformations rather than low-level implementation details.

## Highlights

- High-level, task-oriented syntax with an explicit and documented grammar.
- Variables, mutable state, functions, generic functions, records, entities, and properties.
- Declarative collection operations: filtering, mapping, sorting, aggregates, reduction, and pipelines.
- Modules, imports, exports, and a standard library with 277 public function entries across 13 modules.
- Static semantic and type validation with structured diagnostics.
- Interpreter execution and an in-process LLVM Native JIT for supported programs.
- Language Server Protocol support and editor integrations for Visual Studio Code, Zed, Neovim, and Emacs.
- Self-contained official runtime installers.

## Installation

Install S-Lang using the official package for your operating system.

The Windows runtime executable is named `slang1.0.exe`. On Windows, invoke it directly as:

```text
slang1.0.exe version
slang1.0.exe check main.sl
slang1.0.exe run main.sl
```

On Linux and macOS, the executable is named `slang`:

```text
slang version
slang check main.sl
slang run main.sl
```

The official prebuilt runtime is self-contained. End users do not need to install Python, GCC, Clang, or LLVM separately just to install or run S-Lang.

## First program

Create `main.sl`:

```slang
let name = "S-Lang"
let numbers = [1, 2, 3, 4, 5]
let doubled = numbers map item * 2
let total = doubled sum item
show "Hello from", name
show "Total:", total
```

Validate and run it:

```text
slang check main.sl
slang run main.sl
```

On Windows, replace `slang` with `slang1.0.exe`.

## Native JIT

For supported programs, the in-process LLVM Native JIT can execute without invoking an external C/C++ compiler:

```text
slang run --native-jit main.sl
```

The separate direct native build command may require Clang or GCC. This is a toolchain requirement for that build path, not an installation requirement for the official self-contained runtime.

## Editor integration

The Language Server Protocol service is started with:

```text
slang lsp
```

The source tree includes first-party integrations for Visual Studio Code, Zed, Neovim, and Emacs. They use the compiler/LSP as the authority for diagnostics and language semantics. Editor grammars provide highlighting and structural editing support; they are not independent language specifications.

On Windows, configure the editor to use the installed `slang1.0.exe` if automatic discovery does not find it.

## Developer package

This archive contains the compiler and runtime source, standard library, automated tests, examples, benchmarks, editor integrations, packaging scripts, and build workflows.

Building S-Lang from source is a developer workflow and may require Python, LLVM/llvmlite, and platform build tools. Those requirements do not apply to users installing an official prebuilt runtime.

## Documentation

- [S-Lang 1.0 User Guide and Language Reference (LaTeX)](docs/latex/S-Lang_1.0_User_Manual_EN.tex)
- [Normative Syntax Reference](docs/S-Lang_1.0_Syntax_Reference_EN.md)
- [Design Principles](docs/S-Lang_Design_Principles_EN.md)
- [LaTeX compilation instructions](docs/latex/README_COMPILE_EN.txt)

The LaTeX manual is written entirely in English and can be compiled on Overleaf with XeLaTeX or LuaLaTeX.

## Project structure

```text
slang/          compiler, runtime, standard library, LSP, native backend
runtime/        C runtime source
tests/          automated regression and conformance tests
examples/       example S-Lang programs
benchmarks/     comparison and performance workloads
editors/        first-party editor integrations
packaging/      runtime, installer, and editor packaging
installers/     platform-specific installation notes
docs/           normative references and user documentation
.github/        CI and release workflows
```

## Official distribution

Source repository: https://github.com/mandmidrov-alt/S-Lang-official

Release assets: https://github.com/mandmidrov-alt/S-Lang-official/releases
