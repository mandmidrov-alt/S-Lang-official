# S-Lang 1.0 - Linux x64

S-Lang is a deterministic high-level programming language designed around describing tasks, data, and transformations rather than low-level implementation details.

This package provides the prebuilt S-Lang 1.0 runtime for:

- 64-bit x86 Linux systems
- x86_64 / amd64 architecture

Two package formats are provided:

- .deb - Debian, Ubuntu, and other Debian-based distributions
- .rpm - Fedora, RHEL, openSUSE, and other RPM-based distributions

## Debian / Ubuntu installation

Install the .deb package with:

sudo apt install ./S-Lang-1.0-linux-amd64.deb

After installation, verify:

slang version

## RPM-based Linux installation

Install the .rpm package with your distribution's package manager.

For example:

sudo dnf install ./S-Lang-1.0-linux-x86_64.rpm

On systems using yum:

sudo yum install ./S-Lang-1.0-linux-x86_64.rpm

Verify the installation:

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

The official S-Lang package is self-contained.

You do NOT need to install the following separately just to install or run S-Lang:

- Python
- GCC
- Clang
- LLVM

The legacy native build path (`slang run --native`) is different and may require Clang or GCC.

## Architecture

This package is intended for:

x86_64 / amd64

It is not intended for ARM64 systems.

## Uninstallation

Use your normal package manager.

Debian / Ubuntu:

sudo apt remove slang

RPM-based systems:

sudo dnf remove slang

## Documentation

Full S-Lang 1.0 documentation is distributed separately.

Official release page:

https://github.com/mandmidrov-alt/S-Lang-official/releases

## Source repository

https://github.com/mandmidrov-alt/S-Lang-official
