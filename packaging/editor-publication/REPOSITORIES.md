# S-Lang Editor Public Repositories

The publication trees are intended to become independent repositories. They
must not bundle the S-Lang compiler or runtime; all integrations invoke the
installed `slang` CLI and canonical `slang lsp` server.

| Component | Recommended repository | Publication target |
|---|---|---|
| VS Code | `S-Lang-vscode` | Visual Studio Marketplace |
| Neovim | `S-Lang-neovim` | GitHub/package managers |
| Zed | `S-Lang-zed` | Zed Extensions registry |
| Tree-sitter | `tree-sitter-slang` | GitHub / downstream Tree-sitter users |
| Emacs | `slang-mode` | MELPA / GNU ELPA |

Before pushing a public repository, replace repository URLs and account-specific
metadata with the final values. The source integration under `editors/` remains
the canonical copy inside the main S-Lang development tree until the public
repositories are established.
