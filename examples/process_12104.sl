command_result = run_process_timeout("python -c \"print(42)\"", 5)
program_result = run_program_timeout("python", ["-c", "print(42)"], 5, "")
