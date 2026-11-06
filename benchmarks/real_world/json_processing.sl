let value = json_parse("{\"project\":{\"name\":\"S-Lang\",\"version\":15,\"status\":\"active\"}}")
let version = json_get(value, "project.version", 0)
let updated = json_set(value, "project.release", "stable")
show version, len(json_stringify(updated))
