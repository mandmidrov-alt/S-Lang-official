let result = run_process("printf 'hello\\n'; printf 'error\\n' 1>&2; exit 3")
show result
