// JSON file persistence
config = {"name": "S-Lang", "version": 1.12}
write_json("config.json", config)
loaded = read_json("config.json")
