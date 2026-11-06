"""Transport-neutral Language Server core for S-Lang.

The module deliberately contains no JSON-RPC or socket implementation.  It keeps
LSP document state and delegates parsing/validation to the normal S-Lang compiler
and diagnostic adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from urllib.parse import unquote, urlparse

from .ast import source_span_of
from .lsp_tokens import TOKEN_TYPES, TOKEN_MODIFIERS

from .diagnostics import (
    Diagnostic,
    diagnostics_for_source,
    diagnostics_to_lsp_publish,
)


LSP_SERVER_NAME = "slang"
LSP_SERVER_VERSION = "1.0"


@dataclass(frozen=True)
class LSPDocument:
    uri: str
    text: str
    version: int | None = None


class LSPServer:
    """Minimal transport-neutral S-Lang language-server state machine."""

    def __init__(self, *, name: str = LSP_SERVER_NAME, version: str = LSP_SERVER_VERSION, root_uri: str | None = None):
        self.name = name
        self.version = version
        self.root_uri = root_uri
        self.workspace_folders: tuple[dict, ...] = ()
        self._settings: dict = {}
        self._documents: dict[str, LSPDocument] = {}
        self._dependencies: dict[str, tuple[str, ...]] = {}
        self._dependents: dict[str, tuple[str, ...]] = {}
        self._semantic_token_cache: dict[str, list[tuple[str, tuple[int, ...], int | None]]] = {}
        self._semantic_token_cache_limit = 8
        self._command_edits: dict[str, dict] = {}
        self._workspace_index: dict[str, tuple[dict, ...]] = {}
        self._workspace_index_paths: dict[str, Path] = {}
        self._workspace_index_programs: dict[str, tuple[object, str]] = {}
        self._workspace_index_stats: dict[str, tuple[int, int]] = {}
        self._workspace_semantic_version = 0
        self._parsed_workspace_cache: tuple[int, dict[str, tuple[object, str]]] | None = None
        self._semantic_symbols_cache: tuple[int, tuple[object, ...]] | None = None
        self._shutdown = False
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown

    @property
    def documents(self) -> tuple[LSPDocument, ...]:
        return tuple(self._documents[key] for key in sorted(self._documents))

    @property
    def settings(self) -> dict:
        """Return a defensive copy of the current workspace settings."""
        return _copy_settings(self._settings)

    def did_change_configuration(self, settings: Mapping | None) -> tuple[dict, ...]:
        """Replace workspace settings and republish affected diagnostics."""
        if settings is None:
            self._settings = {}
        elif not isinstance(settings, Mapping):
            raise TypeError("workspace settings must be a mapping")
        else:
            self._settings = _copy_settings(dict(settings))
        return tuple(self.publish_diagnostics(uri) for uri in sorted(self._documents))

    def _invalidate_workspace_semantics(self) -> None:
        """Invalidate derived semantic state after workspace contents/index change."""
        self._workspace_semantic_version += 1
        self._parsed_workspace_cache = None
        self._semantic_symbols_cache = None

    def refresh_workspace_index(self, changed_uris: Iterable[str] | None = None) -> tuple[str, ...]:
        """Refresh the project index, parsing only files whose disk state changed.

        With no explicit URI set, the workspace is scanned for additions and
        deletions, while unchanged files retain their parsed program.  When
        ``changed_uris`` is supplied, only those file URIs are re-read (plus
        removal of entries that no longer exist).
        """
        from .core import parse
        from .lsp_navigation import symbol_information

        roots: set[Path] = set()
        if self.root_uri:
            root = self._uri_path(self.root_uri)
            if root is not None:
                roots.add(root)
        for folder in self.workspace_folders:
            if isinstance(folder, Mapping):
                raw = folder.get("uri")
                path = self._uri_path(raw) if isinstance(raw, str) else None
                if path is not None:
                    roots.add(path)

        discovered: dict[str, Path] = {}
        for root in sorted(roots, key=str):
            if not root.exists() or not root.is_dir():
                continue
            try:
                files = sorted((path for path in root.rglob("*.sl") if path.is_file()), key=str)
            except OSError:
                continue
            for path in files:
                resolved = path.resolve()
                discovered[resolved.as_uri()] = resolved

        explicit = None if changed_uris is None else {uri for uri in changed_uris if isinstance(uri, str)}
        old_paths = dict(self._workspace_index_paths)
        old_stats = dict(self._workspace_index_stats)
        old_programs = dict(self._workspace_index_programs)
        old_symbols = dict(self._workspace_index)

        # Remove deleted files, files outside current workspace roots, and files
        # that became open documents (open state is always authoritative).
        for uri in list(old_programs):
            path = old_paths.get(uri)
            if uri in self._documents or uri not in discovered or (path is not None and not path.exists()):
                old_programs.pop(uri, None)
                old_paths.pop(uri, None)
                old_stats.pop(uri, None)
                old_symbols.pop(uri, None)

        for uri, path in discovered.items():
            if uri in self._documents:
                continue
            try:
                stat = path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                continue
            needs_parse = (
                uri in (explicit or set())
                or uri not in old_programs
                or old_stats.get(uri) != stamp
            )
            if not needs_parse:
                continue
            try:
                text = path.read_text(encoding="utf-8")
                program = parse(text, path.parent)
                old_symbols[uri] = symbol_information(uri, program)
                old_paths[uri] = path
                old_programs[uri] = (program, text)
                old_stats[uri] = stamp
            except (OSError, UnicodeError, Exception):
                # A changed file that temporarily becomes unparsable is removed
                # from the index rather than leaving stale semantic information.
                old_symbols.pop(uri, None)
                old_paths.pop(uri, None)
                old_programs.pop(uri, None)
                old_stats.pop(uri, None)

        self._workspace_index = {uri: old_symbols[uri] for uri in sorted(old_symbols)}
        self._workspace_index_paths = {uri: old_paths[uri] for uri in sorted(old_paths)}
        self._workspace_index_programs = {uri: old_programs[uri] for uri in sorted(old_programs)}
        self._workspace_index_stats = {uri: old_stats[uri] for uri in sorted(old_stats)}
        self._invalidate_workspace_semantics()
        return tuple(sorted(self._workspace_index))

    def refresh_workspace_files(self, uris: Iterable[str]) -> tuple[str, ...]:
        """Incrementally refresh specific file URIs reported by a file watcher."""
        return self.refresh_workspace_index(uris)

    def did_change_watched_files(self, changes: Sequence[Mapping]) -> tuple[dict, ...]:
        """Apply watcher events and propagate semantic/index changes to open documents."""
        if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)):
            raise TypeError("watched file changes must be a sequence")
        affected: set[str] = set()
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            uri = change.get("uri")
            if isinstance(uri, str):
                affected.add(uri)
        before = {uri: tuple(deps) for uri, deps in self._dependencies.items()}
        self.refresh_workspace_files(sorted(affected))
        self._refresh_all_dependencies()
        impacted = self._dependency_impacted_documents(before)
        return self._file_operation_publications_for(impacted)

    def did_create_files(self, files: Sequence[Mapping]) -> tuple[str, ...]:
        """Index newly created S-Lang files reported by LSP file operations."""
        if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
            raise TypeError("created files must be a sequence")
        uris = sorted({item.get("uri") for item in files if isinstance(item, Mapping) and isinstance(item.get("uri"), str)})
        self._apply_file_operation_refresh(uris)
        return tuple(sorted(self._workspace_index))

    def did_create_publications(self, files: Sequence[Mapping]) -> tuple[dict, ...]:
        """Refresh a create operation and publish diagnostics for changed open documents."""
        self.did_create_files(files)
        return self._file_operation_publications()

    def did_delete_files(self, files: Sequence[Mapping]) -> tuple[str, ...]:
        """Remove deleted S-Lang files from the project index."""
        if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
            raise TypeError("deleted files must be a sequence")
        uris = sorted({item.get("uri") for item in files if isinstance(item, Mapping) and isinstance(item.get("uri"), str)})
        for uri in uris:
            if uri in self._documents:
                continue
            self._workspace_index.pop(uri, None)
            self._workspace_index_paths.pop(uri, None)
            self._workspace_index_programs.pop(uri, None)
            self._workspace_index_stats.pop(uri, None)
        self._apply_file_operation_refresh(uris)
        return tuple(sorted(self._workspace_index))

    def did_rename_files(self, files: Sequence[Mapping]) -> tuple[str, ...]:
        """Apply file renames, removing old index entries and indexing new paths."""
        if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
            raise TypeError("renamed files must be a sequence")
        old_uris: set[str] = set()
        new_uris: set[str] = set()
        for item in files:
            if not isinstance(item, Mapping):
                continue
            old_uri = item.get("oldUri")
            new_uri = item.get("newUri")
            if isinstance(old_uri, str):
                old_uris.add(old_uri)
            if isinstance(new_uri, str):
                new_uris.add(new_uri)
        for uri in sorted(old_uris):
            if uri in self._documents:
                continue
            self._workspace_index.pop(uri, None)
            self._workspace_index_paths.pop(uri, None)
            self._workspace_index_programs.pop(uri, None)
            self._workspace_index_stats.pop(uri, None)
        # A rename can make previously unresolved imports resolve (or become
        # unresolved), so perform an incremental workspace scan and rebuild the
        # dependency graph. Unchanged indexed programs remain cached.
        self._apply_file_operation_refresh((*old_uris, *new_uris))
        return tuple(sorted(self._workspace_index))

    def did_rename_publications(self, files: Sequence[Mapping]) -> tuple[dict, ...]:
        """Refresh a rename operation and publish diagnostics for changed open documents."""
        self.did_rename_files(files)
        return self._file_operation_publications()

    def _dependency_impacted_documents(self, before: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
        """Return open documents whose dependency graph changed and invalidate derived state."""
        impacted = tuple(sorted(
            uri for uri in self._documents
            if before.get(uri, ()) != self._dependencies.get(uri, ())
        ))
        for uri in impacted:
            # Navigation/completion/symbols are computed from current state and have
            # no persistent cache. Semantic-token delta history does, so invalidate it.
            self._semantic_token_cache.pop(uri, None)
        return impacted

    def _file_operation_publications_for(self, impacted: Iterable[str]) -> tuple[dict, ...]:
        return tuple(
            self.publish_diagnostics(uri)
            for uri in sorted(set(impacted))
            if uri in self._documents
        )

    def _apply_file_operation_refresh(self, uris: Iterable[str]) -> None:
        """Refresh the index and invalidate LSP-derived state affected by dependency changes."""
        before = {uri: tuple(deps) for uri, deps in self._dependencies.items()}
        self.refresh_workspace_index(tuple(uris))
        self._refresh_all_dependencies()
        self._last_file_operation_impacted = self._dependency_impacted_documents(before)

    def _file_operation_publications(self) -> tuple[dict, ...]:
        """Publish diagnostics only for open documents affected by the latest file operation."""
        return self._file_operation_publications_for(getattr(self, "_last_file_operation_impacted", ()))

    def _all_symbol_entries(self) -> tuple[dict, ...]:
        from .core import parse
        from .lsp_navigation import symbol_information
        result = []
        for uri in sorted(self._workspace_index):
            result.extend(self._workspace_index[uri])
        for uri in sorted(self._documents):
            document = self._documents[uri]
            path = self._uri_path(uri)
            try:
                program = parse(document.text, path.parent if path is not None else None)
                result.extend(symbol_information(uri, program))
            except Exception:
                continue
        return tuple(result)

    def did_change_workspace_folders(self, event: Mapping) -> tuple[dict, ...]:
        """Apply an LSP workspace-folder change event deterministically."""
        if not isinstance(event, Mapping):
            raise TypeError("workspace folder event must be a mapping")
        current = {folder.get("uri"): dict(folder) for folder in self.workspace_folders if isinstance(folder, Mapping) and isinstance(folder.get("uri"), str)}
        for folder in event.get("removed", ()) or ():
            if isinstance(folder, Mapping) and isinstance(folder.get("uri"), str):
                current.pop(folder["uri"], None)
        for folder in event.get("added", ()) or ():
            if isinstance(folder, Mapping) and isinstance(folder.get("uri"), str):
                current[folder["uri"]] = dict(folder)
        self.workspace_folders = tuple(current[key] for key in sorted(current))
        self.refresh_workspace_index()
        return self.workspace_folders

    def initialize(self, *, client_capabilities: Mapping | None = None, root_uri: str | None = None, workspace_folders: Iterable[Mapping] | None = None) -> dict:
        self._initialized = True
        self._shutdown = False
        if root_uri is not None:
            self.root_uri = root_uri
        self.workspace_folders = tuple(dict(folder) for folder in (workspace_folders or ()))
        self.refresh_workspace_index()
        self._refresh_all_dependencies()
        return {
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 2, "save": {"includeText": True}},
                "workspace": {"workspaceFolders": {"supported": True, "changeNotifications": True}, "fileOperations": {
                    "didCreate": {"filters": [{"scheme": "file", "pattern": {"glob": "**/*.sl", "matches": "file"}}]},
                    "didRename": {"filters": [{"scheme": "file", "pattern": {"glob": "**/*.sl", "matches": "file"}}]},
                    "didDelete": {"filters": [{"scheme": "file", "pattern": {"glob": "**/*.sl", "matches": "file"}}]},
                }},
                "configuration": True,
                "documentSymbolProvider": True,
                "workspaceSymbolProvider": True,
                "definitionProvider": True,
                "referencesProvider": True,
                "hoverProvider": True,
                "completionProvider": {"triggerCharacters": ["."]},
                "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
                "codeActionProvider": {"codeActionKinds": ["quickfix"]},
                "documentHighlightProvider": True,
                "inlayHintProvider": {"resolveProvider": False},
                "renameProvider": {"prepareProvider": True},
                "documentLinkProvider": {"resolveProvider": False},
                "executeCommandProvider": {"commands": ["slang.applyWorkspaceEdit"]},
                "semanticTokensProvider": {"legend": {"tokenTypes": list(TOKEN_TYPES), "tokenModifiers": list(TOKEN_MODIFIERS)}, "full": True, "range": True},
            },
            "serverInfo": {"name": self.name, "version": self.version},
        }

    def shutdown(self) -> None:
        self._shutdown = True

    def did_open(self, uri: str, text: str, *, version: int | None = None) -> dict:
        self._semantic_token_cache.pop(uri, None)
        self._documents[uri] = LSPDocument(uri, text, version)
        self._workspace_index.pop(uri, None)
        self._workspace_index_paths.pop(uri, None)
        self._invalidate_workspace_semantics()
        self._refresh_all_dependencies()
        return self.publish_diagnostics(uri)

    def did_change(self, uri: str, text: str | Sequence[Mapping], *, version: int | None = None) -> dict:
        if uri not in self._documents:
            raise KeyError(f"document is not open: {uri}")
        current = self._documents[uri].text
        if isinstance(text, str):
            new_text = text
        else:
            new_text = current
            for change in text:
                new_text = self._apply_text_change(new_text, change)
        self._documents[uri] = LSPDocument(uri, new_text, version)
        self._workspace_index.pop(uri, None)
        self._workspace_index_paths.pop(uri, None)
        self._invalidate_workspace_semantics()
        self._refresh_all_dependencies()
        return self.publish_diagnostics(uri)

    @staticmethod
    def _position_offset(text: str, position: Mapping) -> int:
        line = position.get("line")
        character = position.get("character")
        if not isinstance(line, int) or not isinstance(character, int) or line < 0 or character < 0:
            raise ValueError("invalid LSP text position")
        lines = text.splitlines(keepends=True)
        if line > len(lines):
            raise ValueError("LSP text position is outside the document")
        if line == len(lines):
            if character != 0:
                raise ValueError("LSP text position is outside the document")
            return len(text)
        line_text = lines[line]
        content_len = len(line_text.rstrip("\r\n"))
        if character > content_len:
            raise ValueError("LSP text position is outside the document")
        return sum(len(item) for item in lines[:line]) + character

    @classmethod
    def _apply_text_change(cls, text: str, change: Mapping) -> str:
        replacement = change.get("text")
        if not isinstance(replacement, str):
            raise ValueError("LSP text change requires string text")
        if "range" not in change or change["range"] is None:
            return replacement
        range_value = change["range"]
        if not isinstance(range_value, Mapping):
            raise ValueError("invalid LSP text change range")
        start = range_value.get("start")
        end = range_value.get("end")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            raise ValueError("invalid LSP text change range")
        start_offset = cls._position_offset(text, start)
        end_offset = cls._position_offset(text, end)
        if end_offset < start_offset:
            raise ValueError("LSP text change end precedes start")
        return text[:start_offset] + replacement + text[end_offset:]

    def did_save(self, uri: str, *, text: str | None = None, version: int | None = None) -> dict:
        if uri not in self._documents:
            raise KeyError(f"document is not open: {uri}")
        if text is not None:
            self._documents[uri] = LSPDocument(uri, text, version if version is not None else self._documents[uri].version)
            self._invalidate_workspace_semantics()
            self._refresh_all_dependencies()
        elif version is not None:
            document = self._documents[uri]
            self._documents[uri] = LSPDocument(uri, document.text, version)
        return self.publish_diagnostics(uri)

    def did_close(self, uri: str) -> dict:
        self._remove_document_graph(uri)
        self._documents.pop(uri, None)
        self._semantic_token_cache.pop(uri, None)
        self._invalidate_workspace_semantics()
        self.refresh_workspace_index()
        return {"uri": uri, "diagnostics": []}

    def did_open_publications(self, uri: str, text: str, *, version: int | None = None) -> tuple[dict, ...]:
        self.did_open(uri, text, version=version)
        return self.publish_related_diagnostics(uri)

    def did_change_publications(self, uri: str, text: str, *, version: int | None = None) -> tuple[dict, ...]:
        self.did_change(uri, text, version=version)
        return self.publish_related_diagnostics(uri)


    def _uri_path(self, uri: str) -> Path | None:
        """Convert an LSP file URI to a native path, including Windows drive paths."""
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            return None

        raw_path = unquote(parsed.path)
        # Windows file URIs commonly arrive as file:///C:/path/to/file.
        # pathlib on Windows treats the leading slash in /C:/... as part of
        # the root, producing an invalid path and breaking relative imports.
        if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[1].isalpha() and raw_path[2] == ":":
            raw_path = raw_path[1:]

        if parsed.netloc and parsed.netloc.lower() != "localhost":
            # Preserve UNC paths such as file://server/share/file.sl.
            raw_path = f"//{parsed.netloc}{raw_path}"
        return Path(raw_path).resolve()

    def _refresh_all_dependencies(self) -> None:
        """Rebuild the workspace import graph for open and indexed files."""
        self._dependencies.clear()
        self._dependents.clear()
        for uri in sorted(self._parsed_workspace()):
            self._refresh_dependencies(uri)

    def _refresh_dependencies(self, uri: str) -> None:
        """Refresh one file's imports against the complete workspace index."""
        old = set(self._dependencies.get(uri, ()))
        deps: set[str] = set()
        path = self._uri_path(uri)
        workspace = self._parsed_workspace()
        entry = workspace.get(uri)
        if path is not None and entry is not None:
            try:
                from .project import resolve_import
                program = entry[0]
                candidate_by_path = {
                    self._uri_path(candidate_uri).resolve(): candidate_uri
                    for candidate_uri in workspace
                    if self._uri_path(candidate_uri) is not None
                }
                for imp in getattr(program.ast, "imports", ()):
                    resolved = resolve_import(path.parent, imp.path)
                    if resolved is None:
                        continue
                    candidate_uri = candidate_by_path.get(resolved.resolve())
                    if candidate_uri is not None and candidate_uri != uri:
                        deps.add(candidate_uri)
            except Exception:
                deps = set()
        self._dependencies[uri] = tuple(sorted(deps))
        for dep in old - deps:
            self._dependents[dep] = tuple(x for x in self._dependents.get(dep, ()) if x != uri)
        for dep in deps:
            current = set(self._dependents.get(dep, ()))
            current.add(uri)
            self._dependents[dep] = tuple(sorted(current))

    def _remove_document_graph(self, uri: str) -> None:
        self._dependencies.pop(uri, None)
        self._dependents.pop(uri, None)
        for key, values in list(self._dependents.items()):
            if uri in values:
                self._dependents[key] = tuple(x for x in values if x != uri)
        for key, values in list(self._dependencies.items()):
            if uri in values:
                self._dependencies[key] = tuple(x for x in values if x != uri)

    def dependencies(self, uri: str) -> tuple[str, ...]:
        if uri not in self._documents:
            raise KeyError(f"document is not open: {uri}")
        self._refresh_dependencies(uri)
        return self._dependencies.get(uri, ())

    def dependents(self, uri: str) -> tuple[str, ...]:
        if uri not in self._documents:
            raise KeyError(f"document is not open: {uri}")
        return self._dependents.get(uri, ())

    def publish_related_diagnostics(self, uri: str) -> tuple[dict, ...]:
        if uri not in self._documents:
            raise KeyError(f"document is not open: {uri}")
        impacted = (uri, *self._dependents.get(uri, ()))
        return tuple(self.publish_diagnostics(item) for item in impacted if item in self._documents)

    def document_symbols(self, uri: str) -> tuple[dict, ...]:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .lsp_navigation import document_symbols
        try:
            program = self._local_program_for_lsp(uri)
            return document_symbols(program)
        except Exception:
            # Editor requests must remain safe while the user is typing invalid code.
            return ()

    def workspace_symbols(self, query: str = "") -> tuple[dict, ...]:
        query = query or ""
        result = list(self._all_symbol_entries())
        if query:
            result = [item for item in result if query.lower() in item["name"].lower()]
        return tuple(sorted(result, key=lambda item: (item["name"].lower(), item["location"]["uri"])))

    def definition(self, uri: str, line: int, character: int) -> tuple[dict, ...]:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .lsp_navigation import definition_candidates
        lines = document.text.splitlines()
        if line < 0 or line >= len(lines):
            return ()
        text = lines[line]
        if character < 0 or character > len(text):
            return ()
        left = character
        right = character
        while left > 0 and (text[left-1].isalnum() or text[left-1] == "_"):
            left -= 1
        while right < len(text) and (text[right].isalnum() or text[right] == "_"):
            right += 1
        word = text[left:right]
        if not word:
            return ()
        result = []
        workspace = self._parsed_workspace()
        visible = self._visible_import_symbols(uri)
        for candidate_uri in sorted(workspace):
            candidate_program = workspace[candidate_uri][0]
            try:
                declarations = definition_candidates(candidate_program, word)
            except Exception:
                continue
            for decl in declarations:
                if self._dependencies.get(uri) and candidate_uri != uri and getattr(decl, "name", None) and (candidate_uri, getattr(decl, "name", None)) not in visible:
                    continue
                span = source_span_of(decl)
                if span is None:
                    continue
                end = span.end or span.start
                result.append({"uri": candidate_uri, "range": {"start": {"line": span.start.line-1, "character": span.start.column-1}, "end": {"line": end.line-1, "character": end.column-1}}})
        return tuple(result)

    def hover(self, uri: str, line: int, character: int) -> dict | None:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .lsp_features import hover
        try:
            program = self._local_program_for_lsp(uri)
            return hover(program, document.text, line, character, self._related_programs_for(uri))
        except Exception:
            # Hover is advisory and should not emit JSON-RPC Internal error for invalid source.
            return None

    def _public_related_program(self, program):
        """Return a shallow semantic view exposing only a module's public declarations."""
        from copy import copy

        ast = copy(program.ast)
        declared = list(getattr(ast, "functions", ())) + list(getattr(ast, "entities", ())) + list(getattr(ast, "records", ()))
        explicit = set(getattr(ast, "exports", ()) or ())
        if not explicit:
            return program
        allowed = explicit
        ast.functions = [item for item in getattr(ast, "functions", ()) if getattr(item, "name", None) in allowed]
        ast.entities = [item for item in getattr(ast, "entities", ()) if getattr(item, "name", None) in allowed]
        ast.records = [item for item in getattr(ast, "records", ()) if getattr(item, "name", None) in allowed]
        ast.properties = [item for item in getattr(ast, "properties", ()) if getattr(item, "entity_type", None) in allowed]
        view = copy(program)
        view.ast = ast
        return view

    def _related_programs_for(self, uri: str) -> tuple[object, ...]:
        """Return imported programs transitively, respecting intermediate exports."""
        self._refresh_all_dependencies()
        workspace = self._parsed_workspace()
        ordered: list[object] = []
        seen: set[str] = {uri}
        queue = [(dep, True) for dep in self._dependencies.get(uri, ())]

        def declaration_names(program) -> set[str]:
            ast = program.ast
            return {getattr(item, "name", None) for item in (
                *getattr(ast, "functions", ()),
                *getattr(ast, "entities", ()),
                *getattr(ast, "records", ()),
            )} - {None}

        while queue:
            current, visible = queue.pop(0)
            if current in seen or current not in workspace:
                continue
            seen.add(current)
            program = workspace[current][0]
            ordered.append(self._public_related_program(program))

            explicit = set(getattr(program.ast, "exports", ()) or ())
            child_names = declaration_names(program)
            for dependency in self._dependencies.get(current, ()):
                if dependency in seen or dependency not in workspace:
                    continue
                # With an explicit export list, an intermediate dependency is
                # traversed only when at least one of its declarations is part
                # of that public API. Without an explicit list, existing S-Lang
                # semantics expose the imported declarations and traversal may
                # continue.
                if explicit:
                    child_program = workspace[dependency][0]
                    child_decl_names = declaration_names(child_program)
                    if not (explicit & child_decl_names):
                        continue
                queue.append((dependency, True))
        return tuple(ordered)

    def _local_program_for_lsp(self, uri: str):
        """Parse only declarations originating in the requested document.

        The compiler parser intentionally merges imported declarations into its
        semantic AST. LSP completion/signature help need the consumer's local
        declarations separately so that imported APIs are governed by the
        dependency/export traversal below.
        """
        from .core import parse
        document = self._documents[uri]
        path = self._uri_path(uri)
        local_lines = []
        for line in document.text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("import ") or stripped.startswith("reexport "):
                local_lines.append("")
            else:
                local_lines.append(line)
        local_text = "\n".join(local_lines)
        try:
            return parse(local_text, path.parent if path is not None else None)
        except Exception:
            return parse(document.text, path.parent if path is not None else None)

    def signature_help(self, uri: str, line: int, character: int) -> dict | None:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .core import parse
        from .lsp_features import signature_help
        path = self._uri_path(uri)
        try:
            program = self._local_program_for_lsp(uri)
        except Exception:
            lines = document.text.splitlines()
            prefix_text = "\n".join(lines[:line]) + ("\n" if line > 0 else "")
            program = parse(prefix_text, path.parent if path is not None else None)
        return signature_help(program, document.text, line, character, self._related_programs_for(uri))

    def completion(self, uri: str, line: int, character: int) -> tuple[dict, ...]:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .core import parse
        from .lsp_features import completion_items
        path = self._uri_path(uri)
        try:
            program = self._local_program_for_lsp(uri)
        except Exception:
            # Completion must remain useful while the user is typing an incomplete
            # construct. Parse the completed prefix before the current line.
            lines = document.text.splitlines()
            prefix_text = "\n".join(lines[:line]) + ("\n" if line > 0 else "")
            program = parse(prefix_text, path.parent if path is not None else None)
        return completion_items(program, document.text, line, character, self._related_programs_for(uri))

    def code_actions(self, uri: str, *, diagnostics: Iterable[Mapping] | None = None) -> tuple[dict, ...]:
        """Return deterministic quick fixes for diagnostics that have safe edits."""
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .core import parse
        from .lsp_features import code_actions_for_diagnostics
        path = self._uri_path(uri)
        try:
            program = parse(document.text, path.parent if path is not None else None)
        except Exception:
            program = None
        source_diagnostics = tuple(diagnostics) if diagnostics is not None else self.diagnostics(uri)
        visible_names = {name for _source_uri, name in self._visible_import_symbols(uri)}
        actions = list(code_actions_for_diagnostics(program, document.text, uri, source_diagnostics, extra_names=visible_names))
        actions.extend(self._interfile_code_actions(uri, program, source_diagnostics))
        result = []
        for index, action in enumerate(actions):
            edit = action.get("edit")
            if not isinstance(edit, Mapping):
                result.append(action)
                continue
            command_id = f"slang.quickfix.{len(self._command_edits) + index + 1}"
            self._command_edits[command_id] = _copy_settings(dict(edit))
            updated = dict(action)
            updated.pop("edit", None)
            updated["command"] = {
                "title": action.get("title", "Apply quick fix"),
                "command": "slang.applyWorkspaceEdit",
                "arguments": [command_id],
            }
            result.append(updated)
        return tuple(result)

    def _interfile_code_actions(self, uri: str, program, diagnostics: Iterable[Diagnostic]) -> tuple[dict, ...]:
        """Return safe multi-file quick fixes for selectively imported exports.

        When a module explicitly exports a declaration but a consumer imported a
        selective list that omitted it, the fix updates both files atomically.
        This is intentionally conservative: only open documents and explicit
        export/import declarations are changed.
        """
        import re
        from .project import resolve_import
        document = self._documents.get(uri)
        if document is None:
            return ()
        ast = getattr(program, "ast", None)
        imports = list(getattr(ast, "imports", ()) if ast is not None else ())
        # Virtual/open documents may not have import targets materialized on disk;
        # recover their import declarations directly from source text.
        import re
        seen_imports = {(getattr(item, "path", None), getattr(item, "alias", None), tuple(getattr(item, "names", ()) or ())) for item in imports}
        for match in re.finditer(r'(?m)^\s*import\s+"([^"]+)"(?:\s+as\s+([A-Za-z_]\w*))?(?:\s+\{\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*\})?\s*$', document.text):
            names = tuple(x.strip() for x in match.group(3).split(',')) if match.group(3) else ()
            key = (match.group(1), match.group(2), names)
            if key not in seen_imports:
                imports.append(type("Import", (), {"path": match.group(1), "alias": match.group(2), "names": names})())
        if not imports:
            return ()
        diagnostics_by_name = {}
        for diagnostic in diagnostics:
            code = diagnostic.get("code") if isinstance(diagnostic, Mapping) else getattr(diagnostic, "code", None)
            if code != "E2001":
                continue
            data = diagnostic.get("data", {}) if isinstance(diagnostic, Mapping) else (getattr(diagnostic, "data", {}) or {})
            name = data.get("name")
            if isinstance(name, str):
                diagnostics_by_name.setdefault(name, []).append(diagnostic)
        if not diagnostics_by_name:
            return ()
        result = []
        current_path = self._uri_path(uri)
        if current_path is None:
            return ()
        for imp in imports:
            if not getattr(imp, "names", ()):
                continue
            try:
                target_path = resolve_import(current_path.parent, imp.path)
            except Exception:
                target_path = None
            if target_path is None:
                candidate = (current_path.parent / imp.path).resolve()
                target_path = candidate if candidate.as_uri() in self._documents else None
            if target_path is None:
                continue
            target_uri = target_path.as_uri()
            target_doc = self._documents.get(target_uri)
            if target_doc is None:
                continue
            try:
                target_program = self._parsed_workspace().get(target_uri, (None, ""))[0]
            except Exception:
                target_program = None
            target_ast = getattr(target_program, "ast", None) if target_program is not None else None
            if target_ast is None or not getattr(target_ast, "exports", ()):
                continue
            exported = set(getattr(target_ast, "exports", ()) or ())
            declarations = set()
            for collection in (getattr(target_ast, "functions", ()), getattr(target_ast, "records", ()), getattr(target_ast, "entities", ())):
                declarations.update(getattr(item, "name", None) for item in collection)
            for name, diagnostics_for_name in diagnostics_by_name.items():
                if name in imp.names or name not in exported or name not in declarations:
                    continue
                # Locate the exact import line and export declaration.
                lines = document.text.splitlines()
                import_edit = None
                imp_re = re.compile(r'^(\s*import\s+"' + re.escape(imp.path) + r'"(?:\s+as\s+[A-Za-z_]\w*)?\s*\{)([^}]*)\}(\s*)$')
                for line_no, line_text in enumerate(lines):
                    match = imp_re.match(line_text)
                    if match:
                        names_text = match.group(2).strip()
                        new_names = (names_text + ", " + name) if names_text else name
                        start_char = match.start(2)
                        end_char = match.end(2)
                        import_edit = {"range": {"start": {"line": line_no, "character": start_char}, "end": {"line": line_no, "character": end_char}}, "newText": new_names}
                        break
                if import_edit is None:
                    continue
                target_lines = target_doc.text.splitlines()
                export_edit = None
                export_re = re.compile(r'^(\s*export\s+(?:\{\s*)?)([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)(\s*\}?)\s*$')
                for line_no, line_text in enumerate(target_lines):
                    match = export_re.match(line_text)
                    if match:
                        names_text = match.group(2)
                        new_names = names_text + ", " + name
                        export_edit = {"range": {"start": {"line": line_no, "character": match.start(2)}, "end": {"line": line_no, "character": match.end(2)}}, "newText": new_names}
                        break
                if export_edit is None:
                    continue
                edit = {"changes": {uri: [import_edit], target_uri: [export_edit]}}
                diag_payload = []
                for diagnostic in diagnostics_for_name:
                    if isinstance(diagnostic, Mapping):
                        diag_payload.append(dict(diagnostic))
                        continue
                    span = getattr(diagnostic, "span", None)
                    if span is None:
                        continue
                    end = span.end or span.start
                    diag_payload.append({"code": diagnostic.code, "message": diagnostic.message, "range": {"start": {"line": span.start.line - 1, "character": span.start.column - 1}, "end": {"line": end.line - 1, "character": end.column - 1}}})
                result.append({"title": f"Export '{name}' and add it to the selective import", "kind": "quickfix", "diagnostics": diag_payload, "edit": edit})
        return tuple(result)

    def execute_command(self, command: str, arguments: Sequence | None = None) -> dict | None:
        """Execute a server-registered workspace-edit command.

        The command returns a standard LSP ``WorkspaceEdit`` for the client to
        apply. The server does not mutate editor buffers directly.
        """
        if command != "slang.applyWorkspaceEdit":
            raise KeyError(f"unknown command: {command}")
        args = list(arguments or ())
        if len(args) != 1 or not isinstance(args[0], str):
            raise ValueError("slang.applyWorkspaceEdit requires one command id")
        edit = self._command_edits.get(args[0])
        if edit is None:
            raise KeyError(f"unknown command id: {args[0]}")
        return _copy_settings(edit)

    def references(self, uri: str, line: int, character: int, include_declaration: bool = True) -> tuple[dict, ...]:
        """Resolve references across the complete indexed workspace."""
        target = self._semantic_symbol_at(uri, line, character)
        if target is None:
            return ()
        refs = list(self._semantic_references(target, uri))
        declaration = {"uri": target.uri, "range": target.declaration["range"]}
        if include_declaration:
            if declaration not in refs:
                refs.append(declaration)
        else:
            refs = [item for item in refs if item != declaration]
        return tuple(sorted(refs, key=lambda item: (item["uri"], item["range"]["start"]["line"], item["range"]["start"]["character"])))

    def _word_at_position(self, uri: str, line: int, character: int) -> tuple[str, dict] | None:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        lines = document.text.splitlines()
        if line < 0 or line >= len(lines):
            return None
        source = lines[line]
        if character < 0 or character > len(source):
            return None
        left = right = character
        while left > 0 and (source[left - 1].isalnum() or source[left - 1] == "_"):
            left -= 1
        while right < len(source) and (source[right].isalnum() or source[right] == "_"):
            right += 1
        if left == right:
            return None
        return source[left:right], {"start": {"line": line, "character": left}, "end": {"line": line, "character": right}}

    def _semantic_tokens_payload(self, uri: str, *, start_line: int | None = None, end_line: int | None = None) -> dict:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .core import parse
        from .lsp_tokens import semantic_tokens
        path = self._uri_path(uri)
        try:
            program = parse(document.text, path.parent if path is not None else None)
        except Exception:
            return {"data": []}
        visible_names = None
        if self._dependencies.get(uri):
            visible_names = {name for _source, name in self._visible_import_symbols(uri)}
        return semantic_tokens(program, document.text, start_line=start_line, end_line=end_line, visible_names=visible_names)

    @staticmethod
    def _semantic_result_id(data: list[int]) -> str:
        import hashlib
        import json
        return hashlib.sha256(json.dumps(data, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _semantic_delta(old: tuple[int, ...], new: tuple[int, ...]) -> list[dict]:
        if old == new:
            return []
        prefix = 0
        limit = min(len(old), len(new))
        while prefix < limit and old[prefix] == new[prefix]:
            prefix += 1
        suffix = 0
        while suffix < limit - prefix and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]:
            suffix += 1
        end_old = len(old) - suffix if suffix else len(old)
        replacement = list(new[prefix:len(new) - suffix if suffix else len(new)])
        return [{"start": prefix, "deleteCount": end_old - prefix, "data": replacement}]

    def semantic_tokens(self, uri: str) -> dict:
        payload = self._semantic_tokens_payload(uri)
        data = tuple(payload.get("data", ()))
        result_id = self._semantic_result_id(list(data))
        self._remember_semantic_tokens(uri, result_id, data)
        return {"resultId": result_id, "data": list(data)}

    def _remember_semantic_tokens(self, uri: str, result_id: str, data: tuple[int, ...]) -> None:
        document = self._documents.get(uri)
        version = document.version if document is not None else None
        history = self._semantic_token_cache.setdefault(uri, [])
        history[:] = [item for item in history if item[0] != result_id]
        history.append((result_id, data, version))
        if len(history) > self._semantic_token_cache_limit:
            del history[:-self._semantic_token_cache_limit]

    def semantic_tokens_range(self, uri: str, start_line: int, end_line: int, start_character: int = 0, end_character: int | None = None) -> dict:
        payload = self._semantic_tokens_payload(uri)
        # Decode the generated stream so range filtering can use the complete LSP
        # start/end positions instead of only line numbers.
        filtered: list[int] = []
        data = list(payload.get("data", ()))
        line = 0
        character = 0
        for index in range(0, len(data), 5):
            delta_line, delta_start, length, token_type, modifiers = data[index:index + 5]
            line += delta_line
            character = character + delta_start if delta_line == 0 else delta_start
            token_start = character
            token_end = character + length
            before_start = (line < start_line) or (line == start_line and token_end <= start_character)
            after_end = (line > end_line) or (line == end_line and end_character is not None and token_start >= end_character)
            if not before_start and not after_end:
                filtered.append((line, token_start, length, token_type, modifiers))
        filtered.sort(key=lambda item: (item[0], item[1], item[3]))
        encoded: list[int] = []
        previous_line = 0
        previous_start = 0
        for line, start, length, token_type, modifiers in filtered:
            encoded.extend((line - previous_line, start - previous_start if line == previous_line else start, length, token_type, modifiers))
            previous_line = line
            previous_start = start
        return {"data": encoded}

    def semantic_tokens_delta(self, uri: str, previous_result_id: str | None) -> dict:
        history = self._semantic_token_cache.get(uri, [])
        previous = next((item for item in reversed(history) if item[0] == previous_result_id), None)
        current = self._semantic_tokens_payload(uri)
        current_data = tuple(current.get("data", ()))
        current_id = self._semantic_result_id(list(current_data))
        self._remember_semantic_tokens(uri, current_id, current_data)
        if previous is None:
            return {"resultId": current_id, "data": list(current_data)}
        return {"resultId": current_id, "edits": self._semantic_delta(previous[1], current_data)}

    def inlay_hints(self, uri: str, *, range_start: dict | None = None, range_end: dict | None = None) -> tuple[dict, ...]:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        from .lsp_inlay import inlay_hints
        try:
            program = self._local_program_for_lsp(uri)
            return inlay_hints(program, self._related_programs_for(uri), document.text, range_start=range_start, range_end=range_end)
        except Exception:
            # Inlay hints are optional; invalid or incomplete source must not break LSP.
            return ()

    def document_links(self, uri: str) -> tuple[dict, ...]:
        """Return deterministic links for resolvable source-module imports."""
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        path = self._uri_path(uri)
        if path is None:
            return ()
        from .core import parse
        from .project import resolve_import
        try:
            program = parse(document.text, path.parent)
        except Exception:
            return ()
        links = []
        lines = document.text.splitlines()
        for imp in getattr(program.ast, "imports", ()):
            if imp.path.startswith("std."):
                continue
            target = resolve_import(path.parent, imp.path)
            if target is None:
                continue
            target = target.resolve()
            target_uri = target.as_uri()
            span = source_span_of(imp)
            if span is None:
                continue
            line_index = span.start.line - 1
            if line_index < 0 or line_index >= len(lines):
                continue
            source_line = lines[line_index]
            marker = f'"{imp.path}"'
            marker_pos = source_line.find(marker)
            if marker_pos >= 0:
                start_col = marker_pos + 1
                end_col = start_col + len(imp.path)
            else:
                start_col = max(span.start.column - 1, 0)
                end_col = max((span.end or span.start).column - 1, start_col)
            links.append({
                "range": {
                    "start": {"line": line_index, "character": start_col},
                    "end": {"line": line_index, "character": end_col},
                },
                "target": target_uri,
            })
        return tuple(sorted(links, key=lambda item: (item["range"]["start"]["line"], item["range"]["start"]["character"], item["target"])))

    def document_highlight(self, uri: str, line: int, character: int) -> tuple[dict, ...]:
        # Highlights are semantic rather than textual: unrelated occurrences
        # with the same spelling are not highlighted, and imported symbols must
        # pass the same export-aware visibility rules as definition/references.
        target = self._semantic_symbol_at(uri, line, character)
        if target is None:
            return ()
        refs = list(self._semantic_references(target, source_uri=uri))
        declaration = {"uri": target.uri, "range": target.declaration["range"]}
        if declaration not in refs:
            refs.append(declaration)
        return tuple(
            {"range": item["range"]}
            for item in sorted(refs, key=lambda item: (item["range"]["start"]["line"], item["range"]["start"]["character"]))
            if item["uri"] == uri
        )

    def prepare_rename(self, uri: str, line: int, character: int) -> dict | None:
        # The semantic resolver already enforces the same export-aware visibility
        # rules used by definition/references/hover.  Do not offer rename for a
        # symbol that is not actually visible from the requested document.
        target = self._semantic_symbol_at(uri, line, character)
        if target is None:
            return None
        return {"range": target.declaration["range"], "placeholder": target.name}

    def rename(self, uri: str, line: int, character: int, new_name: str) -> dict | None:
        if not isinstance(new_name, str) or not new_name or not new_name.replace("_", "a").isalnum() or new_name[0].isdigit():
            return None
        target = self._semantic_symbol_at(uri, line, character)
        if target is None:
            return None
        # Do not silently merge with another declaration in the same scope.
        if any(s.name == new_name and s.uri == target.uri and s.scope == target.scope and s != target for s in self._semantic_symbols()):
            return None
        # Resolve references with per-document visibility.  This prevents a
        # private declaration from being renamed merely because its spelling
        # happens to occur in another module.
        edits = list(self._semantic_references(target, source_uri=uri))
        declaration_ref = {"uri": target.uri, "range": target.declaration["range"]}
        if declaration_ref not in edits:
            edits.append(declaration_ref)
        changes = {}
        for ref in edits:
            changes.setdefault(ref["uri"], []).append({"range": ref["range"], "newText": new_name})
        for items in changes.values():
            items.sort(key=lambda item: (item["range"]["start"]["line"], item["range"]["start"]["character"]))
        return {"changes": {key: changes[key] for key in sorted(changes)}}

    def _parsed_workspace(self):
        from .core import parse
        if self._parsed_workspace_cache is not None and self._parsed_workspace_cache[0] == self._workspace_semantic_version:
            return self._parsed_workspace_cache[1]
        # Start with the project index (closed files), then overlay open documents.
        # This makes open editor state authoritative without throwing away the
        # semantic information for the rest of the workspace.
        result = dict(self._workspace_index_programs)
        for uri in sorted(self._documents):
            document = self._documents[uri]
            path = self._uri_path(uri)
            try:
                result[uri] = (parse(document.text, path.parent if path is not None else None), document.text)
            except Exception:
                if path is not None:
                    sanitized = "\n".join("" if line.lstrip().startswith("import ") else line for line in document.text.splitlines())
                    try:
                        result[uri] = (parse(sanitized, path.parent), document.text)
                    except Exception:
                        continue
        self._parsed_workspace_cache = (self._workspace_semantic_version, result)
        return result

    def _semantic_symbols(self):
        from .lsp_semantic import build_index
        if self._semantic_symbols_cache is not None and self._semantic_symbols_cache[0] == self._workspace_semantic_version:
            return self._semantic_symbols_cache[1]
        result = tuple(build_index(self._parsed_workspace()))
        self._semantic_symbols_cache = (self._workspace_semantic_version, result)
        return result

    def _visible_import_symbols(self, uri: str) -> set[tuple[str, str]]:
        """Return public symbols reachable from ``uri`` through imports."""
        visible: set[tuple[str, str]] = set()
        workspace = self._parsed_workspace()
        self._refresh_all_dependencies()

        def declarations(candidate_uri):
            program = workspace.get(candidate_uri, (None, ""))[0]
            if program is None:
                return set()
            names = set()
            ast = program.ast
            for field in ("functions", "entities", "records", "properties"):
                for decl in getattr(ast, field, ()) or ():
                    name = getattr(decl, "name", None)
                    if name:
                        names.add(name)
            return names

        queue = list(self._dependencies.get(uri, ()))
        seen: set[str] = {uri}
        while queue:
            current = queue.pop(0)
            if current in seen or current not in workspace:
                continue
            seen.add(current)
            program = workspace[current][0]
            names = declarations(current)
            explicit = set(getattr(program.ast, "exports", ()) or ())
            allowed = explicit if explicit else names
            for name in sorted(allowed):
                visible.add((current, name))

            for dependency in self._dependencies.get(current, ()):
                if dependency in seen or dependency not in workspace:
                    continue
                child_names = declarations(dependency)
                if explicit and not (explicit & child_names):
                    continue
                queue.append(dependency)
        return visible

    def _semantic_workspace(self):
        """Return a workspace whose program ASTs contain only local declarations."""
        from .core import parse
        workspace = self._parsed_workspace()
        result = {}
        for item_uri, (program, text) in workspace.items():
            if item_uri in self._documents:
                result[item_uri] = (self._local_program_for_lsp(item_uri), text)
                continue
            path = self._uri_path(item_uri)
            lines = text.splitlines()
            sanitized = "\n".join("" if line.lstrip().startswith(("import ", "reexport ")) else line for line in lines)
            try:
                local = parse(sanitized, path.parent if path is not None else None)
            except Exception:
                local = program
            result[item_uri] = (local, text)
        return result

    def _semantic_symbol_at(self, uri: str, line: int, character: int):
        from .lsp_semantic import symbol_at
        workspace = self._semantic_workspace()
        entry = workspace.get(uri)
        if entry is None:
            return None
        visible = self._visible_import_symbols(uri) if self._dependencies.get(uri) else None
        return symbol_at(entry[0], entry[1], uri, line, character, workspace, visible_imports=visible)

    def _semantic_references(self, target, source_uri: str | None = None):
        from .lsp_semantic import resolved_references
        semantic_workspace = self._semantic_workspace()
        if source_uri is None:
            visible = None
        else:
            visible = {item_uri: (self._visible_import_symbols(item_uri) if self._dependencies.get(item_uri) else None) for item_uri in semantic_workspace}
        return resolved_references(semantic_workspace, target, visible_imports=visible)

    def publish_diagnostics(self, uri: str) -> dict:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        path = self._uri_path(uri)
        diagnostics = self._apply_diagnostic_settings(diagnostics_for_source(
            document.text, path=uri, base_dir=path.parent if path is not None else None
        ).diagnostics)
        payload = diagnostics_to_lsp_publish(diagnostics, uri=uri)
        payload["version"] = document.version
        return payload

    def _apply_diagnostic_settings(self, diagnostics: tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
        settings = self._settings
        slang = settings.get("slang", settings) if isinstance(settings, Mapping) else {}
        diagnostic_settings = slang.get("diagnostics", {}) if isinstance(slang, Mapping) else {}
        if not isinstance(diagnostic_settings, Mapping):
            return diagnostics
        if diagnostic_settings.get("enabled") is False:
            return ()
        maximum = diagnostic_settings.get("maxProblems")
        if isinstance(maximum, int) and not isinstance(maximum, bool) and maximum >= 0:
            return diagnostics[:maximum]
        return diagnostics

    def diagnostics(self, uri: str) -> tuple[Diagnostic, ...]:
        document = self._documents.get(uri)
        if document is None:
            raise KeyError(f"document is not open: {uri}")
        path = self._uri_path(uri)
        return self._apply_diagnostic_settings(diagnostics_for_source(
            document.text, path=uri, base_dir=path.parent if path is not None else None
        ).diagnostics)


def _copy_settings(value):
    if isinstance(value, Mapping):
        return {key: _copy_settings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_settings(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_settings(item) for item in value)
    return value


__all__ = ["LSPDocument", "LSPServer", "LSP_SERVER_NAME", "LSP_SERVER_VERSION"]
