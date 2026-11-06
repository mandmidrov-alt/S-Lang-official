# Practical UTF-8 file workflow
let text = read_text("input.txt")
let lines = read_lines("input.txt")
let cleaned = normalize_whitespace(text)
write_text("output.txt", cleaned)
append_text("output.txt", "\nDone")
write_lines("lines.txt", lines)
