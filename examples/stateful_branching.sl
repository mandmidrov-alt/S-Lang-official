# A nested transition function can branch on the current structured state.
entity Step:
    value: Number

function next_step(value: Step) -> Step:
    if value.value < 16:
        return Step(value.value * 2)
    else:
        return Step(value.value + 1)

sequence states from Step(1) for 10 steps using next_step(value)
values = states map item.value
show values
