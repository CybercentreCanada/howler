def test_hit(client):
    res = client.search.histogram.hit(
        "file.size", "id:*", mincount=1, start=0, end=4000, gap=500
    )
    assert isinstance(res, dict)
    for v in res.values():
        assert v >= 1
