from pathlib import Path
import re


def test_native_runtime_exports_public_abi_symbols_on_windows():
    root = Path(__file__).resolve().parents[1]
    sources = [root / "slang" / "slang_runtime.c", root / "runtime" / "slang_runtime.c"]
    required = {
        "slang_csv_open",
        "slang_csv_field_index",
        "slang_csv_count",
        "slang_csv_get_text",
        "slang_csv_free",
        "slang_csv_sort_print",
    }
    for source in sources:
        text = source.read_text(encoding="utf-8")
        assert "#define SLANG_API __declspec(dllexport)" in text
        exported = set(re.findall(r"\bSLANG_API\s+(?:const\s+)?[A-Za-z_]\w*(?:\s*\*)?\s*(slang_[A-Za-z0-9_]+)\s*\(", text))
        assert required <= exported, f"Missing Windows exports in {source}: {sorted(required - exported)}"


def test_runtime_sources_are_identical():
    root = Path(__file__).resolve().parents[1]
    assert (root / "slang" / "slang_runtime.c").read_bytes() == (root / "runtime" / "slang_runtime.c").read_bytes()
