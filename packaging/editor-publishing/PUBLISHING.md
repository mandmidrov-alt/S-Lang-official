# S-Lang 1.0 editor publication checklist

## 1. VS Code

The extension is already structured as a Marketplace extension in
`editors/vscode-slang/`.

Before publication, the maintainer must own a registered VS Code Marketplace
publisher whose identifier matches `package.json` (`publisher`). Then build:

```text
npm install --no-audit --no-fund
npm run validate
npx vsce package
```

The resulting `.vsix` can be tested locally and then uploaded/published through
the VS Code Marketplace publisher account.

The extension does not bundle S-Lang itself. Users install S-Lang separately;
the extension starts `<serverPath> lsp`.

## 2. Neovim

Neovim does not have a single official central marketplace equivalent to the
VS Code Marketplace. The recommended distribution is a public Git repository
whose plugin root contains the contents of `editors/neovim-slang/`.

For example, a plugin manager can then reference the repository directly.
The repository should retain the runtime/plugin directory layout (`plugin/`,
`ftplugin/`, `ftdetect/`, `lua/`).

The S-Lang repository's ZIP is a release/development artifact; it is not
intended to be copied into a user's Neovim installation by hand after the
public repository is available.

## 3. Zed

Zed's current registry requires a dedicated public extension Git repository.
The extension is then submitted as a submodule PR to the official
`zed-industries/extensions` repository.

The S-Lang Zed source currently lives under `editors/zed-slang/`. For registry
publication it should become the root of a dedicated repository, for example:

```text
slang-zed/
├── extension.toml
├── Cargo.toml
├── src/
├── languages/
└── tree-sitter-slang/
```

The Tree-sitter grammar must also be exposed from a public grammar repository
with a fixed Git revision in `extension.toml`; a placeholder revision must not
be published.

After the dedicated repository is ready, submit it to the Zed extension
registry according to the registry's current PR process.

## 4. Emacs

`editors/emacs-slang/slang-mode.el` is a standard Emacs package entry point.
The recommended public source is the S-Lang Git repository. A MELPA recipe can
select `editors/emacs-slang/slang-mode.el` from that repository, or a dedicated
Emacs repository can be used.

After the recipe is accepted, users install `slang-mode` from MELPA using
Emacs's normal package interface.

## Runtime dependency

All four integrations require an installed S-Lang 1.0 runtime/CLI. They do
not replace or duplicate the compiler, standard library, runtime, or LSP
implementation.
