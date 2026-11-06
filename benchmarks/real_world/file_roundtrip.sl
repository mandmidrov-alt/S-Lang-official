let source = "alpha\nbeta\ngamma\n"
let path = ".roundtrip.txt"
let wrote = write(path, source)
let normalized = normalize_whitespace(read(path))
let lines = read_lines(path)
show len(lines), length_text(normalized), count_text(normalized, "a")
