# Direct process execution: no shell command construction.
let result = run_program("printf", ["S-Lang", "direct"], "")
show result
