let logs = ["INFO boot ok", "ERROR disk full", "INFO retry", "WARN latency", "ERROR timeout", "INFO recovered"]
let normalized = logs |> where contains_text(item, "ERROR") |> map lower(item)
let count = normalized count
show count, length_text(join_texts(normalized, "|"))
