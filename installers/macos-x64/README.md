# S-Lang 1.0 - macOS x64

S-Lang is a deterministic high-level programming language designed around describing tasks, data, and transformations rather than low-level implementation details.

This package provides the prebuilt S-Lang 1.0 runtime for:

- macOS on Intel processors
- x86_64 architecture

## Installation

Open:

S-Lang-1.0-macos-x64.pkg

Follow the macOS installer instructions.

After installation, open a new Terminal window.

Verify:

slang version

## Creating your first project

Initialize a project:

slang init my-app --name my-app --version 0.1.0

Enter the project directory:

cd my-app

Check an S-Lang source file:

slang check src/main.sl

Run the program:

slang run src/main.sl

For supported programs, self-contained native JIT execution is also available:

slang run --native-jit src/main.sl

## Requirements

The official S-Lang installer is self-contained.

You do NOT need to install the following separately just to install or run S-Lang:

- Python
- GCC
- Clang
- LLVM

The legacy native build path (`slang run --native`) is different and may require a system C/C++ compiler.

## Architecture

This package is intended for:

Intel x86_64

For Apple Silicon Macs, use the ARM64 package instead.

## Uninstallation

S-Lang can be removed using the standard macOS package management procedures.

## Documentation

Full S-Lang 1.0 documentation is distributed separately.

Official release page:

https://github.com/mandmidrov-alt/S-Lang-official/releases

## Source repository

https://github.com/mandmidrov-alt/S-Lang-official
