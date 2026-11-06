# S-Lang Language Support for Visual Studio Code

First-party editor integration for S-Lang 1.0.

The extension uses the canonical S-Lang Language Server:

```text
slang lsp
```

The compiler/runtime is not bundled with the extension. Install S-Lang separately and make `slang` available on `PATH`, or configure `slang.serverPath`.

## Features

- `.sl` language recognition;
- syntax highlighting and snippets;
- automatic Language Server startup and shutdown;
- project discovery through `slang.toml`;
- workspace-aware LSP configuration;
- diagnostics, completion, hover, definitions and references;
- rename, symbols, semantic tokens, code actions and inlay hints;
- Run/Check current file;
- Run/Check project;
- Run project with native LLVM JIT;
- VS Code Tasks for project Run, Check and Native JIT;
- project information command;
- project initialization command;
- Language Server restart command.

## Project workflow

Create a project:

```text
slang init my-app --name my-app --version 0.1.0
cd my-app
code .
```

The extension detects `slang.toml`, reads its `entry` field, starts `slang lsp`, and exposes project tasks.

The standard generated project is:

```text
my-app/
├── slang.toml
├── README.md
└── src/
    └── main.sl
```

Open **Terminal → Run Task** to see:

- `S-Lang: Run Project`
- `S-Lang: Check Project`
- `S-Lang: Run Project with Native JIT`

## Commands

- `S-Lang: Run Current File`
- `S-Lang: Check Current File`
- `S-Lang: Run Current File with Native JIT`
- `S-Lang: Run Project`
- `S-Lang: Check Project`
- `S-Lang: Run Project with Native JIT`
- `S-Lang: Show Project Information`
- `S-Lang: Initialize Project`
- `S-Lang: Restart Language Server`

## Configuration

```json
{
  "slang.serverPath": "slang",
  "slang.diagnostics.enabled": true,
  "slang.diagnostics.maxProblems": 100,
  "slang.project.autoStartLanguageServer": true
}
```

For a non-standard installation, set `slang.serverPath` to the S-Lang executable.

## Packaging

From this directory:

```text
npm install
npm run validate
npm run package
```

The result is a `.vsix` package suitable for direct installation into Visual Studio Code.
## Executable setup

On Windows, the extension looks for `slang1.0.exe` in the workspace and nearby build folders. On Linux and macOS, it looks for `slang`. If it finds one, it saves the absolute path to VS Code User settings. If it cannot find one (or finds multiple candidates), it asks you to choose the executable. You can change it later with **S-Lang: Configure Executable** from the Command Palette.

