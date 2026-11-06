# Publishing S-Lang for Neovim

The plugin can be distributed directly from a public Git repository and discovered through common Neovim plugin managers.

Recommended repository name: `S-Lang-neovim`.

The plugin should remain dependency-light and invoke the installed `slang lsp` executable rather than bundling S-Lang.

Users can install it with their preferred plugin manager by referencing the public repository. The exact installation declaration depends on the manager (for example, lazy.nvim or packer.nvim).
