from slang import LSPJsonRpcServer


def init(rpc):
    return rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})


def open_doc(rpc, uri, text, version=1):
    rpc.handle_message({"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":uri,"version":version,"text":text}}})


def full(rpc, uri, previous=None, request_id=2):
    params={"textDocument":{"uri":uri}}
    if previous is not None:
        params["previousResultId"]=previous
    return rpc.handle_message({"jsonrpc":"2.0","id":request_id,"method":"textDocument/semanticTokens/full","params":params})[0]["result"]


def test_range_filters_characters_not_only_lines(tmp_path):
    uri=(tmp_path/"main.sl").as_uri()
    rpc=LSPJsonRpcServer(); init(rpc); open_doc(rpc,uri,"let alpha = 1\nlet beta = 2\n")
    result=rpc.handle_message({"jsonrpc":"2.0","id":2,"method":"textDocument/semanticTokens/range","params":{"textDocument":{"uri":uri},"range":{"start":{"line":0,"character":4},"end":{"line":0,"character":9}}}})[0]["result"]
    assert result["data"]
    assert result["data"][0] == 0


def test_delta_accepts_result_id_from_older_cached_version(tmp_path):
    uri=(tmp_path/"main.sl").as_uri()
    rpc=LSPJsonRpcServer(); init(rpc); open_doc(rpc,uri,"let one = 1\n",1)
    first=full(rpc,uri,request_id=2)
    rpc.handle_message({"jsonrpc":"2.0","method":"textDocument/didChange","params":{"textDocument":{"uri":uri,"version":2},"contentChanges":[{"text":"function two() { return 2 }\n"}]}})
    second=full(rpc,uri,request_id=3)
    rpc.handle_message({"jsonrpc":"2.0","method":"textDocument/didChange","params":{"textDocument":{"uri":uri,"version":3},"contentChanges":[{"text":"function three() { return 3 }\n"}]}})
    delta=full(rpc,uri,first["resultId"],4)
    assert "edits" in delta
    assert delta["resultId"] != first["resultId"]
    assert second["resultId"] != first["resultId"]


def test_full_result_reuses_same_result_id_without_duplicate_history(tmp_path):
    uri=(tmp_path/"main.sl").as_uri()
    rpc=LSPJsonRpcServer(); init(rpc); open_doc(rpc,uri,"let value = 1\n",1)
    first=full(rpc,uri,request_id=2)
    second=full(rpc,uri,request_id=3)
    assert first["resultId"] == second["resultId"]
    delta=full(rpc,uri,first["resultId"],4)
    assert delta["edits"] == []
