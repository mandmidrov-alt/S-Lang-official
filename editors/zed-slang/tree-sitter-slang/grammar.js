// S-Lang 1.0 editor grammar.
// This grammar is for editor parsing/highlighting. The compiler and LSP remain
// authoritative for indentation, typing, and semantic validation.
module.exports = grammar({
  name: 'slang',

  extras: $ => [/[ \t\r\n]+/, $.comment],

  rules: {
    source_file: $ => repeat($._statement),

    _statement: $ => choice(
      $.module_declaration, $.import_declaration, $.export_declaration,
      $.function_declaration, $.property_declaration,
      $.record_declaration, $.entity_declaration,
      $.state_declaration, $.set_statement, $.let_declaration,
      $.if_statement,
      $.return_statement, $.show_statement,
      $.data_declaration, $.graph_declaration, $.physics_declaration,
      $.body_declaration, $.simulate_statement, $.sequence_statement, $.sequence_choice_statement,
      $.choose_statement, $.path_statement, $.satisfy_statement,
      $.circle_declaration, $.assignment, $.collection_statement,
      $.expression_statement, $.field_declaration, $.data_row
    ),

    module_declaration: $ => seq('module', $.qualified_name),
    import_declaration: $ => seq('import', choice($.string, $.qualified_name), optional(seq('as', $.identifier)), optional($.import_names)),
    import_names: $ => seq('{', commaSep1($.identifier), '}'),
    export_declaration: $ => seq('export', choice(commaSep1($.identifier), seq(optional('{'), commaSep1($.identifier), optional('}'), 'from', $.string))),

    function_declaration: $ => seq('function', $.identifier, optional($.generic_parameters), '(', optional(commaSep1($.parameter)), ')', optional(seq('->', $.type_ref)), ':'),
    parameter: $ => seq($.identifier, optional(seq(':', $.type_ref))),
    generic_parameters: $ => seq('<', commaSep1($.identifier), '>'),
    property_declaration: $ => seq('property', $.identifier, '.', $.identifier, optional(seq('->', $.type_ref)), ':'),
    record_declaration: $ => seq('record', $.identifier, optional($.generic_parameters), ':'),
    entity_declaration: $ => seq('entity', $.identifier, ':'),
    field_declaration: $ => seq($.identifier, ':', $.type_ref),
    type_ref: $ => seq($.qualified_name, optional(seq('<', commaSep1($.type_ref), '>'))),

    state_declaration: $ => seq('state', $.identifier, '=', $._expression),
    set_statement: $ => seq('set', $.identifier, '=', $._expression),
    let_declaration: $ => seq('let', $.identifier, '=', $._expression),
    assignment: $ => seq($.identifier, '=', $._expression),
    if_statement: $ => seq('if', $._expression, ':'),
    return_statement: $ => seq('return', optional($._expression)),
    show_statement: $ => seq('show', commaSep1($._expression)),

    data_declaration: $ => seq('data', $.identifier, ':'),
    data_row: $ => seq($.identifier, repeat1(seq($.identifier, $._expression_atom))),
    graph_declaration: $ => seq('graph', $.identifier, ':'),
    physics_declaration: $ => seq('physics', $.identifier),
    body_declaration: $ => seq('body', $.identifier, ':'),
    simulate_statement: $ => seq('simulate', $.identifier, 'around', $.identifier, 'for', $._expression, $.identifier, 'step', $._expression, $.identifier),
    sequence_statement: $ => seq('sequence', $.identifier, 'from', $._expression, 'for', optional('up'), optional('to'), $._expression, 'steps', optional(seq('until', $._expression)), 'using', $._expression),
    sequence_choice_statement: $ => seq('sequence', $.identifier, 'from', $._expression, 'for', 'up', 'to', $._expression, 'steps', 'toward', $._expression, 'choosing', ':'),
    choose_statement: $ => seq(optional(seq($.identifier, '=')), 'choose', $.identifier, 'from', $.identifier, optional(seq('where', $._expression)), choice('minimizing', 'maximizing'), $._expression),
    path_statement: $ => seq($.identifier, '=', 'find', 'path', 'from', $.identifier, 'to', $.identifier, 'in', $.identifier, 'minimizing', 'cost'),
    satisfy_statement: $ => seq(optional(seq($.identifier, '=')), 'satisfy', ':'),
    circle_declaration: $ => seq('circle', $.identifier, ':'),

    collection_statement: $ => seq(optional(seq('let', $.identifier, '=')), $.identifier, choice(
      seq('where', $._expression), seq('map', $._expression),
      seq('sort', 'by', $._expression, optional(choice('asc', 'desc'))),
      seq(choice('sum', 'count', 'max', 'min', 'average', 'avg', 'any', 'all'), optional($._expression)),
      seq('reduce', $._expression, 'with', $._expression)
    )),
    pipeline_expression: $ => seq($._expression_atom, '|>', $.pipeline_stage, repeat(seq('|>', $.pipeline_stage))),
    pipeline_stage: $ => choice(
      seq('where', $.pipeline_predicate),
      seq('map', $.pipeline_value),
      seq('sort', 'by', $.pipeline_value, optional(choice('asc', 'desc'))),
      seq(choice('sum', 'count', 'max', 'min', 'average', 'avg', 'any', 'all'), optional($.pipeline_value)),
      seq('reduce', $._expression, 'with', $._expression),
      seq('tee', $.identifier),
      $.conditional_pipeline_stage
    ),
    // In pipeline context, a leading operator is shorthand for an operation
    // on the current item; .field is shorthand for item.field.
    pipeline_predicate: $ => choice(
      $._expression,
      seq(choice('==', '!=', '<', '>', '<=', '>=', '+', '-', '*', '/', '%'), $._expression_atom),
      seq('.', $.identifier, repeat(seq('.', $.identifier)), optional(seq(choice('==', '!=', '<', '>', '<=', '>='), $._expression_atom)))
    ),
    pipeline_value: $ => choice(
      $._expression,
      seq(choice('+', '-', '*', '/', '%'), $._expression_atom),
      seq('.', $.identifier, repeat(seq('.', $.identifier)))
    ),
    conditional_pipeline_stage: $ => seq(
      'if', $._expression, 'then', choice($.pipeline_branch, $.pipeline_stage),
      'else', choice($.pipeline_branch, $.pipeline_stage)
    ),
    pipeline_branch: $ => seq('(', $.pipeline_stage, repeat(seq('|>', $.pipeline_stage)), ')'),

    expression_statement: $ => $._expression,
    _expression: $ => choice($.pipeline_expression, $.conditional_expression, $.logical_or_expression),
    conditional_expression: $ => seq('if', $._expression, 'then', $._expression, 'else', $._expression),
    logical_or_expression: $ => prec.left(1, seq($.logical_and_expression, repeat(seq('or', $.logical_and_expression)))),
    logical_and_expression: $ => prec.left(2, seq($.comparison_expression, repeat(seq('and', $.comparison_expression)))),
    comparison_expression: $ => prec.left(3, seq($.additive_expression, optional(seq(choice('==', '!=', '<', '>', '<=', '>='), $.additive_expression)))),
    additive_expression: $ => prec.left(4, seq($.multiplicative_expression, repeat(seq(choice('+', '-'), $.multiplicative_expression)))),
    multiplicative_expression: $ => prec.left(5, seq($.unary_expression, repeat(seq(choice('*', '/', '%'), $.unary_expression)))),
    unary_expression: $ => choice(seq(choice('-', '+'), $.unary_expression), $.power_expression),
    power_expression: $ => prec.right(6, seq($._expression_atom, optional(seq('^', $.unary_expression)))),
    _expression_atom: $ => choice($.number, $.string, $.boolean, $.identifier, $.call_expression, $.property_expression, $.array, $.record_literal, $.parenthesized_expression, $.not_expression),
    not_expression: $ => seq('not', $._expression_atom),
    call_expression: $ => seq($.qualified_name, '(', optional(commaSep1($._expression)), ')'),
    property_expression: $ => seq($.identifier, repeat1(seq('.', $.identifier))),
    array: $ => seq('[', optional(commaSep1($._expression)), ']'),
    record_literal: $ => seq('{', optional(commaSep1($.record_field)), '}'),
    record_field: $ => seq(choice($.identifier, $.string), ':', $._expression),
    parenthesized_expression: $ => seq('(', $._expression, ')'),
    number: _ => token(/(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?(?:\s*[A-Za-z][A-Za-z0-9_]*)?/),
    string: _ => token(choice(/"([^"\\]|\\.)*"/, /'([^'\\]|\\.)*'/)),
    boolean: _ => choice('true', 'false'),
    qualified_name: $ => seq($.identifier, repeat(seq('.', $.identifier))),
    identifier: _ => /[A-Za-z_][A-Za-z0-9_]*/,
    comment: _ => token(seq('#', /.*/)),
  }
});

function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}
