# S-Lang 1.0 Editor Publication Plan

The editor integrations are distributed independently from the S-Lang runtime.

| Editor | Public distribution | Runtime dependency |
|---|---|---|
| VS Code | Visual Studio Marketplace | installed `slang` |
| Neovim | public Git repository / plugin managers | installed `slang` |
| Zed | Zed Extensions registry | installed `slang` |
| Emacs | public Git repository / package archives such as MELPA | installed `slang` + Eglot |

The Developer archive keeps the integration source under `editors/`. The publication repositories are derived from those directories and should be versioned separately.

No editor package contains the S-Lang compiler/runtime. Every integration ultimately connects to the canonical `slang lsp` command.
