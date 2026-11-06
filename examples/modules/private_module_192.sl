module private_demo
export public_fn

function public_fn(x: Number) -> Number:
    return x * 2

function hidden_fn(x: Number) -> Number:
    return x * 3
