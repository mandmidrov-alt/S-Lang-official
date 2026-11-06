# S-Lang Editor Ecosystem (1.0)

S-Lang uses the Language Server Protocol as the common editor integration layer.

The canonical language server is started with:

```text
slang lsp
```

On Windows, use `slang1.0.exe lsp` when the `slang` command alias is not available. On Linux and macOS, use `slang lsp`.

The compiler/runtime remains editor-independent. Editor integrations provide the user interface while the S-Lang CLI and LSP remain the source of language semantics and diagnostics. Editor grammars are updated for the 1.0 syntax surface; they provide highlighting and structural parsing only, not an independent validator.

## Visual Studio Code

The first-party extension is in:

```text
editors/vscode-slang/
```

It provides:

- `.sl` language recognition;
- syntax highlighting and snippets;
- automatic LSP startup/shutdown;
- project discovery through `slang.toml`;
- workspace-aware settings;
- diagnostics, completion, hover, navigation and rename;
- semantic tokens, code actions and inlay hints;
- current-file Run/Check;
- project Run/Check;
- native LLVM JIT Run;
- VS Code Tasks;
- project information and initialization commands;
- VSIX packaging.

## Project model

A standard S-Lang project is:

```text
project/
├── slang.toml
├── README.md
└── src/
    └── main.sl
```

The manifest's `entry` field determines the project entry point. The editor integration uses that same field rather than maintaining a second project configuration.

## Neovim

The first-party Neovim integration is in `editors/neovim-slang/`. It uses Neovim's built-in LSP client and the same canonical server. It provides project discovery, diagnostics, completion/navigation through LSP, and commands for run/check/native-JIT workflows.

## Emacs

The first-party Emacs integration is in `editors/emacs-slang/`. It provides a `slang-mode` major mode and uses Eglot with the canonical `slang lsp` server. It includes project discovery through `slang.toml`, diagnostics/completion/navigation through LSP, and commands for file/project run, check and native-JIT workflows.

## Other editors

All editor integrations use the same canonical LSP command:

```text
slang lsp
```

Editor-specific packages can therefore be added without changing the S-Lang compiler or language semantics.

## Zed

The first-party Zed extension is in `editors/zed-slang/`. Its Tree-sitter grammar and highlight queries are updated for S-Lang 1.0. The compiler/LSP remains authoritative for indentation-sensitive block structure and semantic diagnostics.

It provides `.sl` recognition, Tree-sitter syntax highlighting, and the same canonical
`slang lsp` server used by VS Code and Neovim. The Zed extension is a thin Rust/WASM
adapter; it contains no language semantics of its own.

## Distribution packages

The repository can build ready-to-install editor packages with:

```text
python packaging/build-editor-packages.py --version 1.0.0
```

The resulting `dist/editors/` directory contains:

- `S-Lang-Neovim-1.0.0.zip` — Neovim plugin;
- `slang-mode-1.0.0.tar.gz` — Emacs `slang-mode` package;
- `S-Lang-Zed-1.0.0.zip` — Zed extension source package.

The VS Code integration is packaged separately as a `.vsix` using `vsce`. Old prebuilt VSIX files are not kept in the source archive; build a fresh package from the current extension source:

```text
cd editors/vscode-slang
npm install
npm run package
```

The GitHub Actions workflow `editor-packages.yml` builds all four distribution artifacts for `v1.0.*` tags and manual runs.

### Installation from the packages

VS Code: install the generated `.vsix` through **Extensions → Install from VSIX...**.

Neovim: extract `S-Lang-Neovim-1.0.0.zip` into the Neovim `site/pack/s-lang/start/` directory so that the extracted directory is named `slang-neovim`.

Emacs: extract `slang-mode-1.0.0.tar.gz`, add its directory to `load-path`, and use `(require 'slang-mode)`.

Zed: install the extension from the packaged source through the Zed extension development/install workflow. The extension continues to use the canonical `slang lsp` server.

## Editor branding

The editor ecosystem uses the S-Lang editor icon with the simplified `< S-L >`
mark for small UI surfaces. The master raster asset is kept at
`branding/s-lang-editor-icon.png`; the VS Code extension packages its own copy
as `icon.png` for Marketplace/VSIX branding.

The `//` marker is intentionally omitted from the small editor icon so that it
remains legible at 16–32 px. The full S-Lang logo may still use `//` in larger
branding materials.
