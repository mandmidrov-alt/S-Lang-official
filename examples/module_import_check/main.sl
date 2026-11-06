module module_import_check

import "modules/api.sl" as api
import "modules/core.sl" { triple }
import "modules/core.sl" as direct

let transitive_result = api.add(10, 5)
let selective_result = triple(7)
let namespace_result = direct.add(20, 22)

show transitive_result
show selective_result
show namespace_result

if transitive_result == 15 and selective_result == 21 and namespace_result == 42:
    show "MODULE IMPORT CHECK PASS"
else:
    show "MODULE IMPORT CHECK FAILED"
