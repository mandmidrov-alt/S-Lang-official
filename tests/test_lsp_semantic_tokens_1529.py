from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})


def open_doc(rpc, uri, text):
    rpc.handle_message({"jsonrpc":"2.0", "method":"textDocument/didOpen", "params":{"textDocument":{"uri":uri,"version":1,"text":text}}})


def decode(data):
    out=[]; line=0; char=0
    for i in range(0,len(data),5):
        dl,dc,length,typ,mods=data[i:i+5]
        line += dl
        char = char + dc if dl == 0 else dc
        out.append((line,char,length,typ,mods))
    return out


def types_for(rpc):
    return init(rpc)[0]["result"]["capabilities"]["semanticTokensProvider"]["legend"]["tokenTypes"]


def test_initialize_advertises_semantic_tokens():
    rpc=LSPJsonRpcServer()
    provider=init(rpc)[0]["result"]["capabilities"]["semanticTokensProvider"]
    assert provider["full"] is True
    assert provider["range"] is True
    assert "function" in provider["legend"]["tokenTypes"]
    assert "parameter" in provider["legend"]["tokenTypes"]
    assert "variable" in provider["legend"]["tokenTypes"]


def test_semantic_tokens_classify_declarations_and_keywords(tmp_path):
    uri=(tmp_path/"main.sl").as_uri()
    text="function add(x: Number) -> Number:\n    let total = x + 1\n    return total\n"
    rpc=LSPJsonRpcServer(); init(rpc); open_doc(rpc,uri,text)
    result=rpc.handle_message({"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/full","params":{"textDocument":{"uri":uri}}})[0]["result"]
    types=init(LSPJsonRpcServer())[0]["result"]["capabilities"]["semanticTokensProvider"]["legend"]["tokenTypes"]
    lookup={(line,char,length):types[typ] for line,char,length,typ,_ in decode(result["data"])}
    assert lookup[(0,0,8)] == "keyword"
    assert lookup[(0,9,3)] == "function"
    assert lookup[(0,13,1)] == "parameter"
    assert lookup[(0,16,6)] == "type"
    assert lookup[(1,4,3)] == "keyword"
    assert lookup[(1,8,5)] == "variable"
    assert lookup[(1,16,1)] == "parameter"
    assert lookup[(1,20,1)] == "number"
    assert lookup[(2,4,6)] == "keyword"
    assert lookup[(2,11,5)] == "variable"


def test_semantic_tokens_classify_types_properties_literals_and_calls(tmp_path):
    uri=(tmp_path/"main.sl").as_uri()
    text="record Point:\n    x: Number\n    y: Number\n\nlet p = Point(1, 2)\nlet value = p.x + 2\n"
    rpc=LSPJsonRpcServer(); init(rpc); open_doc(rpc,uri,text)
    result=rpc.handle_message({"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/full","params":{"textDocument":{"uri":uri}}})[0]["result"]
    types=init(LSPJsonRpcServer())[0]["result"]["capabilities"]["semanticTokensProvider"]["legend"]["tokenTypes"]
    lookup={(line,char,length):types[typ] for line,char,length,typ,_ in decode(result["data"])}
    assert lookup[(0,0,6)] == "keyword"
    assert lookup[(0,7,5)] == "type"
    assert lookup[(1,4,1)] == "property"
    assert lookup[(1,7,6)] == "type"
    assert lookup[(4,8,5)] == "type"
    assert lookup[(4,14,1)] == "number"
    assert lookup[(5,14,1)] == "property"
    assert lookup[(5,18,1)] == "number"


def test_semantic_tokens_are_deterministic(tmp_path):
    uri=(tmp_path/"main.sl").as_uri(); text="let value = 42\n"
    rpc=LSPJsonRpcServer(); init(rpc); open_doc(rpc,uri,text)
    msg={"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/full","params":{"textDocument":{"uri":uri}}}
    first=rpc.handle_message(msg)[0]["result"]
    second=rpc.handle_message({**msg,"id":3})[0]["result"]
    assert first == second


def test_semantic_comment_tokens_cover_entire_line_including_letter_n():
    from slang.lsp_tokens import _lex

    text = "# comment contains n and\\n and continues\n// another comment with n\nlet value = 1\n"
    comments = [token for token in _lex(text) if token.kind == "comment"]
    assert [token.text for token in comments] == [
        "# comment contains n and\\n and continues",
        "// another comment with n",
    ]
