def test_hit(client):
    res = sorted([x for x in client.search.stream.hit("id:*")], key=lambda k: k["id"])
    assert len(res) > 0
