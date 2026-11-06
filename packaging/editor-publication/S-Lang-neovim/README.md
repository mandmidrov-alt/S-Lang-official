# S-Lang Neovim Integration

First-party Neovim integration for S-Lang 1.0 using the canonical Language Server:

```text
slang lsp
```

## Requirements

- Neovim 0.10 or newer.
- S-Lang 1.0 installed and available as `slang` on `PATH`, or configured explicitly.
- No external LSP plugin is required.

The integration uses Neovim's built-in LSP client. On Neovim 0.11+ it uses `vim.lsp.config`/`vim.lsp.enable`; on older supported versions it falls back to `vim.lsp.start`.

## Installation

Copy `editors/neovim-slang/` into a Neovim plugin directory or install it with a local/plugin-manager path.

For a manual installation:

```text
~/.local/share/nvim/site/pack/s-lang/start/slang-neovim/
```

On Windows, use the equivalent Neovim `site/pack/.../start/` directory.

## Configuration

The default command is:

```text
slang lsp
```

To use a custom executable, add to `init.lua` before loading the plugin:

```lua
vim.g.slang_server_path = "/path/to/slang"
```

Or explicitly configure the module:

```lua
require("slang").setup({
  server_path = "/path/to/slang",
})
```

## Project support

The integration detects the nearest `slang.toml` and uses its `entry` field. If `entry` is not present, the default is:

```text
src/main.sl
```

A normal project is:

```text
project/
├── slang.toml
└── src/
    └── main.sl
```

## Commands

For the current file:

```text
:SlangRun
:SlangCheck
:SlangRunNativeJit
```

For the current project:

```text
:SlangRunProject
:SlangCheckProject
:SlangRunProjectNativeJit
```

Project initialization:

```text
:SlangInit
```

Diagnostics, completion, hover, definition, references, rename and other LSP features come from the same `slang lsp` implementation used by VS Code.

## Architecture

```text
Neovim
  │
  ├── built-in LSP client ───── slang lsp
  │
  └── project commands ──────── slang run/check/init
                                  │
                               S-Lang 1.0
```

No Neovim-specific compiler or semantic implementation is maintained.
