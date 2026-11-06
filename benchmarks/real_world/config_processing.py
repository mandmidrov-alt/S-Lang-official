config = {"service":{"port":8080,"workers":4,"mode":"prod"}}
port = config["service"]["port"]
workers = config["service"]["workers"]
updated = {**config, "service": {**config["service"], "workers": workers+2}}
new_workers = updated["service"]["workers"]
print(port); print(workers); print(new_workers); print(len("{\"service\":{\"mode\":\"prod\",\"port\":8080,\"workers\":6}}"))
