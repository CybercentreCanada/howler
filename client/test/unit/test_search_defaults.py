from howler_client.module.search import Search


class DummyConnection:
    def __init__(self):
        self.last_path = None

    def get(self, path, **kwargs):
        self.last_path = path
        # Return shapes expected by callers (dicts)
        return {}


def test_facet_default_query_uses_howler_id_star():
    conn = DummyConnection()
    search = Search(conn)

    # Omit query to trigger default path
    search.facet.hit("file.hash.md5")

    assert conn.last_path is not None
    assert "query=howler.id:%2A" in conn.last_path


def test_grouped_default_query_uses_howler_id_star():
    conn = DummyConnection()
    search = Search(conn)

    # Omit query to trigger default path
    search.grouped.hit("file.hash.sha256")

    assert conn.last_path is not None
    assert "query=howler.id:%2A" in conn.last_path


def test_stats_default_query_uses_howler_id_star():
    conn = DummyConnection()
    search = Search(conn)

    # Omit query to trigger default path
    search.stats.hit("file.size")

    assert conn.last_path is not None
    assert "query=howler.id:%2A" in conn.last_path
