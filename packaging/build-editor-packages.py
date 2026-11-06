#!/usr/bin/env python3
"""Build distributable S-Lang editor integration packages."""
from __future__ import annotations

import argparse
import shutil
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "editors"

PACKAGES = {
    "neovim": ROOT / "editors" / "neovim-slang",
    "emacs": ROOT / "editors" / "emacs-slang",
    "zed": ROOT / "editors" / "zed-slang",
}


def zip_dir(source: Path, target: Path, root_name: str) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, Path(root_name) / path.relative_to(source))


def tar_dir(source: Path, target: Path, root_name: str) -> None:
    with tarfile.open(target, "w:gz") as archive:
        archive.add(source, arcname=root_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    zip_dir(
        PACKAGES["neovim"],
        OUT / f"S-Lang-Neovim-{args.version}.zip",
        "slang-neovim",
    )
    tar_dir(
        PACKAGES["emacs"],
        OUT / f"slang-mode-{args.version}.tar.gz",
        "slang-mode",
    )
    zip_dir(
        PACKAGES["zed"],
        OUT / f"S-Lang-Zed-{args.version}.zip",
        "slang-zed",
    )

    # VS Code is intentionally not fabricated here: a valid VSIX must be
    # produced by `vsce package` with its npm dependency tree. The CI workflow
    # publishes the official VSIX artifact.
    manifest = OUT / "README.txt"
    manifest.write_text(
        "S-Lang editor packages\\n"
        "============================\\n\\n"
        f"Version: {args.version}\\n\\n"
        "Neovim: S-Lang-Neovim-{0}.zip\\n"
        "Emacs:  slang-mode-{0}.tar.gz\\n"
        "Zed:    S-Lang-Zed-{0}.zip\\n\\n"
        "VS Code: build with npm install && npm run package in editors/vscode-slang.\\n"
        "The resulting .vsix is the official VS Code install package.\\n".format(args.version),
        encoding="utf-8",
    )
    print(f"Editor packages written to {OUT}")
    for path in sorted(OUT.iterdir()):
        print(f"- {path.name}: {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
