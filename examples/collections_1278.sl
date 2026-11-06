# Select the earliest task by priority while keeping the original task value.

let tasks = [
    {name: "review", priority: 3},
    {name: "build", priority: 1},
    {name: "test", priority: 2},
    {name: "deploy", priority: 1}
]

let next_task = min_by_values(tasks, task -> task.priority)
print(next_task)
