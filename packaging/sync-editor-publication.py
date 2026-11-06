#!/usr/bin/env python3
"""Synchronize first-party editor integrations into publication trees.

The publication trees are deliberately separate from the main source tree so
that each editor integration can be released independently. All integrations
continue to target the canonical `slang lsp` server. This helper keeps
the implementation files synchronized while preserving publication-only files
such as PUBLISHING.md and repository metadata.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "vscode": (ROOT / "editors" / "vscode-slang", ROOT / "packaging/editor-publication/S-Lang-vscode"),
    "neovim": (ROOT / "editors" / "neovim-slang", ROOT / "packaging/editor-publication/S-Lang-neovim"),
    "zed": (ROOT / "editors" / "zed-slang", ROOT / "packaging/editor-publication/S-Lang-zed"),
    "emacs": (ROOT / "editors" / "emacs-slang", ROOT / "packaging/editor-publication/slang-mode"),
}

PRESERVE = {
    "vscode": {"PUBLISHING.md", "LICENSE", "CHANGELOG.md", "README.md", "package.json"},
    "neovim": {"PUBLISHING.md", "README.md"},
    "zed": {"PUBLISHING.md", "README.md", "Cargo.toml", "extension.toml"},
    "emacs": {"PUBLISHING.md", "README.md", "slang-mode.el"},
}


def sync(name: str) -> None:
    source, target = PAIRS[name]
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if any(part in {"__pycache__", ".pytest_cache"} for part in rel.parts):
            continue
        if path.is_dir():
            continue
        dest = target / rel
        if rel.name in PRESERVE[name] and dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    print(f"synced {name}: {source} -> {target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", choices=sorted(PAIRS), default=sorted(PAIRS))
    args = parser.parse_args()
    for name in args.names:
        sync(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
