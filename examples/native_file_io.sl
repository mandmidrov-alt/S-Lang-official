let path = "native_slang_test.txt"
let written = write(path, "S-Lang native I/O")
let present = exists(path)
let size = file_size(path)
let regular = is_file(path)
show written, present, size, regular
