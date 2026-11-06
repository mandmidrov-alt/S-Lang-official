logs = ["INFO boot ok", "ERROR disk full", "INFO retry", "WARN latency", "ERROR timeout", "INFO recovered"]
errors = [x for x in logs if "ERROR" in x]
normalized = [x.lower() for x in errors]
print(len(errors))
print(len("|".join(normalized)))
