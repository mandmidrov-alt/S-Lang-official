# S-Lang 1.0 — Windows x64

This package installs the self-contained S-Lang 1.0 runtime on Windows 10 or later, x64.

## Installation

Run `S-Lang-1.0-Windows-x64-Setup.exe` and follow the installer instructions. Close and reopen the terminal after installation.

The installed executable is named `slang1.0.exe`. Verify the installation:

```text
slang1.0.exe version
```

## First project

```text
slang1.0.exe init my-app --name my-app --version 0.1.0
cd my-app
slang1.0.exe check src/main.sl
slang1.0.exe run src/main.sl
```

For programs supported by the in-process native backend:

```text
slang1.0.exe run --native-jit src/main.sl
```

## Requirements

The official installer is self-contained. Python, GCC, Clang, and LLVM do not need to be installed separately to install or run S-Lang.

The separate direct native build path (`run --native`) may require a system C/C++ compiler.

## Installation location and PATH

The runtime is installed for the current Windows user. The installer can add its installation directory to the user's PATH. Invoke the installed executable as `slang1.0.exe`.

## Uninstallation

Open **Settings → Apps → Installed apps**, find **S-Lang**, and select **Uninstall**.

## Documentation and source

Documentation and release assets:
https://github.com/mandmidrov-alt/S-Lang-official/releases

Source repository:
https://github.com/mandmidrov-alt/S-Lang-official
