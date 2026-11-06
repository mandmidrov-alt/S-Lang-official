from pathlib import Path
source = "alpha\nbeta\ngamma\n"
p = Path("benchmarks/real_world/.roundtrip.txt")
p.write_text(source, encoding="utf-8")
loaded = p.read_text(encoding="utf-8")
normalized = " ".join(loaded.split())
print(len(loaded.splitlines()))
print(len(normalized))
print(normalized.count("a"))
