"""Keep executable S-Lang examples in the English S-Lang 1.0 manual valid."""
from pathlib import Path
import re

from slang.core import parse, validate


def test_standalone_slang_listings_parse_and_validate():
    root = Path(__file__).parents[1]
    manual = root / "docs" / "latex" / "S-Lang_1.0_User_Manual_EN.tex"
    assert manual.is_file()
    source = manual.read_text(encoding="utf-8")
    blocks = re.findall(
        r"\\begin\{lstlisting\}(\[[^]]*\])?\s*(.*?)\\end\{lstlisting\}",
        source,
        re.DOTALL,
    )

    checked = 0
    for options, code in blocks:
        if options and "language={}" in options:
            continue
        code = code.strip("\n")
        if not code.strip():
            continue
        if re.search(r"^(module |import |export )", code, re.MULTILINE):
            continue
        validate(parse(code))
        checked += 1

    assert checked >= 30
