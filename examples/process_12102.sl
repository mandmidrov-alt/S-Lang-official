name = "SLANG_EXAMPLE_ENV"
set_environment(name, "enabled")
exists = has_environment(name)
value = environment(name)
remove_environment(name)
