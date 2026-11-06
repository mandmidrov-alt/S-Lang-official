# 1.2.1: compact value selection without a statement-level branch.
function label(score: Number):
    return if score >= 90 then "excellent" else if score >= 75 then "good" else "basic"

let score = 88
let status = label(score)
show status
