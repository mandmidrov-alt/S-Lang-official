# S-Lang Zed Extension

First-party Zed integration for S-Lang 1.0.

The extension uses the canonical S-Lang Language Server:

```text
slang lsp
```

## Features

- `.sl` file recognition;
- S-Lang syntax highlighting through Tree-sitter;
- diagnostics;
- completion;
- hover;
- go to definition;
- references;
- rename;
- semantic tokens and other LSP features exposed by `slang lsp`;
- project-aware LSP through Zed worktrees;
- `slang.toml` remains the canonical project manifest.

## Requirements

Install S-Lang 1.0 or a compatible later 1.0 release and make `slang` available on `PATH` (on Windows, configure `slang1.0.exe`).

The extension launches:

```text
slang lsp
```

No second language server is bundled.

## Development installation

Open Zed's Extensions page and use the development-extension installation flow with this directory as the extension source.

The extension contains a small Tree-sitter grammar under:

```text
editors/zed-slang/tree-sitter-slang/
```

Before publishing, replace `REPLACE_WITH_RELEASE_COMMIT` in `extension.toml` with the Git commit containing the grammar.

## Project workflow

A normal project remains:

```text
project/
├── slang.toml
└── src/
    └── main.sl
```

Zed uses the same `slang.toml` and the same `slang lsp` implementation as the VS Code and Neovim integrations.

## Architecture

```text
Zed
  │
  ├── Tree-sitter grammar ───── syntax structure/highlighting
  │
  └── S-Lang LSP ────────────── slang lsp
                                  │
                               S-Lang 1.0
```
