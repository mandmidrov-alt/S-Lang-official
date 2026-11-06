from __future__ import annotations

from pathlib import PurePath


def basename(value: str) -> str:
    return PurePath(value).name


def dirname(value: str) -> str:
    parent = PurePath(value).parent
    return str(parent) if str(parent) else "."


def extension(value: str) -> str:
    return PurePath(value).suffix


def join_path(first: str, second: str) -> str:
    return str(PurePath(first) / second)


def normalize_path(value: str) -> str:
    # PurePath does not touch the filesystem; resolve-style absolute paths are
    # deliberately excluded so this operation remains deterministic and pure.
    return str(PurePath(value))
