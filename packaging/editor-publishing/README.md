# S-Lang 1.0 editor publishing

This directory contains the publication checklist and staging rules for the
first-party S-Lang editor integrations.

The integrations are intentionally separate from the S-Lang runtime. Each
editor uses the installed `slang` executable and the canonical `slang lsp`
command.

## Publication targets

- VS Code: Visual Studio Marketplace (`.vsix` is the installable package).
- Neovim: public Git repository, consumed by Neovim plugin managers.
- Zed: a dedicated public Zed extension repository submitted to the official
  `zed-industries/extensions` registry.
- Emacs: public Git repository, then a MELPA recipe submission.

The S-Lang repository contains the source integrations and CI packaging, but
publishing requires the maintainer's external accounts and repository access.
