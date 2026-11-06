# S-Lang 1.0 Editor Publication Repositories

This directory contains publication-ready repository trees for the first-party S-Lang 1.0 editor integrations.

- `S-Lang-vscode/` — Visual Studio Code Marketplace extension
- `S-Lang-neovim/` — Neovim plugin
- `S-Lang-zed/` — Zed language extension
- `tree-sitter-slang/` — dedicated Tree-sitter grammar repository used by Zed
- `slang-mode/` — Emacs package

All integrations use the installed S-Lang CLI and the canonical `slang lsp` language server. The editor packages do not bundle the S-Lang runtime.

Before public release, replace any publisher/account-specific placeholders with the actual maintainer identities and repository URLs.

## Public repository transition

The publication trees are now treated as standalone repository roots. The
repository plan and release targets are documented in `REPOSITORIES.md`.

Branding uses the simplified `< S-L >` editor icon without the `//` marker so
that the mark remains legible at small sizes. The VS Code package declares this
asset as its extension icon.
