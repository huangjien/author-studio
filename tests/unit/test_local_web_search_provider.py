from src.tools.providers.local_web_search import web_search


def test_local_web_search_indexed_query_top_n_limit():
    res = web_search(query="hello", top_n=1)
    assert res["tool"] == "web_search"
    assert res["query"] == "hello"
    assert isinstance(res["results"], list)
    assert len(res["results"]) == 1
    assert res["results"][0]["title"]


def test_local_web_search_fallback_for_unknown_query():
    res = web_search(query="some unknown query", top_n=5)
    assert res["tool"] == "web_search"
    assert res["query"] == "some unknown query"
    assert isinstance(res["results"], list)
    assert len(res["results"]) == 1  # fallback returns single synthetic result
    assert "Result for:" in res["results"][0]["title"]
    assert "example.org/search" in res["results"][0]["url"]


def test_local_web_search_top_n_zero_returns_empty_list():
    res = web_search(query="python", top_n=0)
    assert res["tool"] == "web_search"
    assert isinstance(res["results"], list)
    assert res["results"] == []
