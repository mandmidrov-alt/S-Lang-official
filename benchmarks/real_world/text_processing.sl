let raw = "  S-Lang   makes   data   processing   concise.  "
let lowered = lower(normalize_whitespace(raw))
let words = split(lowered, " ")
let replaced = replace(lowered, "concise", "clear")
show len(words), count_text(lowered, "a"), length_text(replaced)
