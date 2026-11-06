from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)


ROOT = Path(__file__).resolve().parents[2]


hiddenimports = sorted(
    set(
        collect_submodules("slang")
        + [
            "llvmlite",
            "llvmlite.binding",
            "llvmlite.binding.ffi",
        ]
    )
)


datas = (
    collect_data_files(
        "slang",
        include_py_files=False,
    )
    + copy_metadata("slang-language")
)
