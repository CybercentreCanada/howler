from utils import create_hit_and_get_id


def test_hit(client):
    hit_id = create_hit_and_get_id(client)
    res = client.search.grouped.hit("id", query="id:{}".format(hit_id), fl="id")
    assert res["total"] == 1
    assert res["items"][0]["value"] == hit_id

    res = client.search.grouped.hit("file.hash.sha256", query="id:*", offset=1)
    assert res["total"] > 1
