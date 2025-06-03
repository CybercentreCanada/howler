from utils import create_hit_and_get_id


def test_hit(client):
    hit_id = create_hit_and_get_id(client)
    res = client.search.hit("howler.id:{}".format(hit_id))

    assert res["total"] == 1
    assert res["items"][0]["howler"]["id"] == hit_id

    res = client.search.hit("howler.id:*", offset=5)
    assert res["total"] > 1
