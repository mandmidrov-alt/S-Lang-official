// Practical file management in S-Lang 1.12.92
let source = "input.txt"
let backup = "output/backup.txt"
let moved = "output/final.txt"

let created = make_directories("output")
let copied = copy_file(source, backup)
let transferred = move_file(backup, moved)
