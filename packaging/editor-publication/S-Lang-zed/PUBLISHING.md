# Publishing S-Lang for Zed

1. Create a public Git repository for this extension.
2. Create a separate public Git repository for `tree-sitter-slang`.
3. Replace the Tree-sitter repository URL and `rev` in `extension.toml` with the actual public repository and commit.
4. Test the extension in Zed as a dev extension at the exact commit to be submitted.
5. Fork `zed-industries/extensions`.
6. Add this extension as a Git submodule under `extensions/slang`.
7. Add the matching version to `extensions.toml`.
8. Run the registry repository's sorting checks and open a PR.

The extension must not bundle the S-Lang language server. It expects `slang` to be available in the user's environment and uses the canonical `slang lsp` server.


The Tree-sitter grammar source must be published as a standalone grammar repository and its immutable commit SHA inserted into `extension.toml` before Zed registry submission. The placeholder revision is intentionally not treated as a released grammar.
