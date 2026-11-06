value = {"user": {"name": "Dmitry", "settings": {"theme": "dark"}}}
name = json_get(value, "user.name", "unknown")
updated = json_set(value, "user.settings.language", "ru")
exists = json_has(updated, "user.settings.language")
