" S-Lang 1.0.88 syntax highlighting fallback for Neovim.
" Semantic diagnostics and completion remain provided by `slang lsp`.

if exists('b:current_syntax')
  finish
endif

syntax case match

syntax keyword slangKeyword let state set show if then else for while return
syntax keyword slangKeyword function record entity property data graph physics body circle
syntax keyword slangKeyword simulate sequence module import export private from as in
syntax keyword slangKeyword where map sort by asc desc reduce sum count max min average avg any all tee
syntax keyword slangKeyword choose minimizing maximizing find path satisfy until steps step using cost value
syntax keyword slangOperatorWord and or not
syntax keyword slangBoolean true false none null
syntax keyword slangSelf item row acc self
syntax match slangNumber /\<\d\+\%([.]\d\+\)\?\%([eE][+-]\?\d\+\)\?\>/
syntax match slangOperator /|>\|<->\|->\|==\|!=\|<=\|>=\|=>\|\.\.\|[+*/%^=<>:-]/
syntax match slangFunction /\<[A-Za-z_][A-Za-z0-9_]*\ze\s*(/
syntax match slangTypeUnit /\<\(kg\|m\|m2\|s\|mps\|mps2\|N\|m3_per_kg_s2\|second\|seconds\|minute\|minutes\|hour\|hours\|day\|days\)\>/
syntax region slangString start=/"/ skip=/\\./ end=/"/ oneline
syntax region slangString start=/'/ skip=/\\./ end=/'/ oneline
syntax match slangComment /#.*/

highlight default link slangKeyword Keyword
highlight default link slangOperatorWord Operator
highlight default link slangBoolean Boolean
highlight default link slangSelf Special
highlight default link slangNumber Number
highlight default link slangOperator Operator
highlight default link slangFunction Function
highlight default link slangTypeUnit Type
highlight default link slangString String
highlight default link slangComment Comment

let b:current_syntax = 'slang'
