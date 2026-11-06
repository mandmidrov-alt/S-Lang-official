; S-Lang 1.0.88 Tree-sitter highlight queries.
(comment) @comment
(string) @string
(number) @number
(boolean) @constant

["let" "state" "set" "show" "if" "then" "else" "for" "while" "return"
 "function" "record" "entity" "property" "data" "graph" "physics" "body"
 "circle" "simulate" "sequence" "module" "import" "export" "private"
 "from" "as" "in" "where" "map" "sort" "by" "asc" "desc"
 "reduce" "sum" "count" "max" "min" "average" "avg" "any" "all"
 "tee" "choose" "minimizing" "maximizing" "find" "path" "satisfy"
 "until" "steps" "step" "using" "cost" "value"] @keyword

["and" "or" "not"] @keyword.operator
(identifier) @variable
(qualified_name) @namespace
(function_declaration (identifier) @function)
(record_declaration (identifier) @type)
(entity_declaration (identifier) @type)
(call_expression (qualified_name) @function)
(property_expression (identifier) @property)
