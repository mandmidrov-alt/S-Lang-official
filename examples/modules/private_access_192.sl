module demo
import "private_module_192.sl" as p
let x = p.hidden_fn(4)
show x
