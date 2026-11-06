import json
value = {"project":{"name":"S-Lang","version":15,"status":"active"}}
version = value["project"]["version"]
updated = json.loads(json.dumps(value)); updated["project"]["release"] = "stable"
print(version)
print(len(json.dumps(updated, separators=(",", ":"), ensure_ascii=False)))
