module demo
import "private_module_192.sl" { hidden_fn }
let x = hidden_fn(4)
show x
