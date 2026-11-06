# S-Lang 1.12.79: max_by_values

let tasks = [
    { name: "backup", priority: 2 },
    { name: "incident", priority: 10 },
    { name: "report", priority: 5 }
]

let urgent_task = max_by_values(tasks, task -> task.priority)
print(urgent_task.name)
