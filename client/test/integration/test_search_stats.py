def test_hit(client):
    res = client.search.stats.hit("file.size", query="id:*")
    keys = list(res.keys())
    keys.sort()
    assert keys == ["avg", "count", "max", "min", "sum"]
    for v in res.values():
        assert isinstance(v, int) or isinstance(v, float)
