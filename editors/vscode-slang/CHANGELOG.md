# Changelog

## 1.0.0
- Update syntax highlighting for the S-Lang 1.0 language surface.
- Add highlighting for records, entities, properties, modules, imports/exports, state, sequences, graph and physics declarations, collection operations, pipeline stages, units, and logical operators.
- Align comment and string highlighting with the compiler lexer.
- Keep compiler diagnostics and semantic behavior delegated to the canonical S-Lang Language Server.

# Changelog

## 1.0.2
- Automatically discovers `slang1.0.exe` on Windows and `slang` on Unix-like systems in common project/build locations.
- Prompts to select the executable when it cannot be found and saves the absolute path to User settings.
- Adds the `S-Lang: Configure Executable` command for changing the path later.
- Initializes diagnostics and language-server auto-start settings without overwriting existing user values.

1.0.1
- Report Language Server termination explicitly in the S-Lang output channel.
- Keep the editor extension package version aligned with the rebuilt VSIX.
- Pair with the runtime LSP resilience fix: semantic requests on incomplete/invalid source return safe protocol fallbacks instead of repeated internal errors.

## 1.0.0
- Initial S-Lang language support, syntax highlighting, project commands, and Language Server integration.
