let input = read("input.txt")
let lines = read_lines("input.txt")
let output = join(lines, ", ")
let written = write("output.txt", output)
let present = exists("output.txt")
show present
