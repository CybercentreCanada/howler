from utils import create_hit_and_get_id


def test_hit(client):
    hit_id = create_hit_and_get_id(client)
    res = client.search.facet.hit("file.hash.md5", "id:{}".format(hit_id), mincount=1)
    assert isinstance(res, dict)
    for v in res.values():
        assert v >= 1
