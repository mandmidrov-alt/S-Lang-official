# Task-oriented text normalization and line processing.

raw = "  first\t line\nsecond   line  "
clean = normalize_whitespace(raw)
lines = split_lines("first\nsecond\nthird")
output = join_lines(lines)

print(clean)
print(output)
