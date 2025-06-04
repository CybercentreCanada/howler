def test_hit(client):
    res = client.search.fields.hit()
    assert isinstance(res, dict)
    for v in res.values():
        assert "default" in v
        assert "indexed" in v
        assert "list" in v
        assert "stored" in v
        assert "type" in v
