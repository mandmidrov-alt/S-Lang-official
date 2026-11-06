# S-Lang for Emacs

This directory contains the first-party Emacs integration for S-Lang.
It provides a lightweight `slang-mode` major mode and uses Emacs Eglot as the
LSP client. The language server is always the canonical S-Lang command:

```text
slang lsp
```

## Requirements

- Emacs 29 or newer is recommended.
- Eglot is required. It is bundled with modern Emacs releases.
- S-Lang 1.0 must be installed and `slang` must be available on `PATH`, or
  `slang-server-command` can be customized.

## Installation

Copy `slang-mode.el` into a directory on `load-path`, then add:

```elisp
(require 'slang-mode)
```

For a local checkout:

```elisp
(add-to-list 'load-path "/path/to/S-Lang/editors/emacs-slang")
(require 'slang-mode)
```

Opening a `.sl` file activates `slang-mode`. Eglot can then be started with:

```text
M-x slang-start-lsp
```

or `M-x eglot`.

## Commands

| Command | Purpose |
|---|---|
| `slang-start-lsp` | Start/connect to `slang lsp` |
| `slang-run-file` | Run the current file |
| `slang-check-file` | Check the current file |
| `slang-run-native-jit` | Run the current file with native LLVM JIT |
| `slang-run-project` | Run the project from its `slang.toml` root |
| `slang-check-project` | Check the project |
| `slang-run-project-native-jit` | Run the project with native JIT |
| `slang-init-project` | Run `slang init` |
| `slang-show-project-info` | Run `slang project` |

The project root is discovered from the nearest `slang.toml`.

## Key bindings

- `C-c C-l` — start LSP
- `C-c C-r` — run current file
- `C-c C-c` — check current file
- `C-c C-j` — native JIT
- `C-c C-p r` — run project
- `C-c C-p c` — check project
- `C-c C-p j` — project native JIT
- `C-c C-p i` — initialize project
- `C-c C-p p` — project information

## Architecture

Emacs is only the editor/client layer. S-Lang semantics remain in the compiler,
CLI and canonical language server, so the Emacs integration stays aligned with
VS Code, Neovim and Zed.

## Custom S-Lang executable

If `slang` is not on `PATH`, customize:

```elisp
(setq slang-server-command "/path/to/slang")
```

The same executable is then used for `slang lsp`, file commands, and project commands.
