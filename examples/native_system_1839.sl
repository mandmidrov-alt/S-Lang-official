let source = "native_input.txt"
let lines = read_lines(source)
let ok = write_lines("native_output.txt", lines)
let base = basename("workspace/data.txt")
let dir = dirname("workspace/data.txt")
let ext = extension("workspace/data.txt")
let joined = join_path("workspace", "data.txt")
let normalized = normalize_path("workspace//data.txt")
show ok
show base
show dir
show ext
show joined
show normalized
