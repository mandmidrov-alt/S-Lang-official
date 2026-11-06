entity State:
    x: Number
    y: Number
    phase: Number

function next_state(value: State) -> State:
    if value.phase == 0:
        if value.x < 16:
            return State(value.x + 1, value.y + value.x, 0)
        else:
            return State(value.x, value.y, 1)
    else:
        return State(value.x - 1, value.y + 2, 1)

sequence states from State(1, 2, 0) for 20 steps using next_state(value)
xs = states map item.x
scores = states map item.x + item.y
large = scores where item >= 11
total = large reduce 0 with acc + item
show xs, scores, large, total
