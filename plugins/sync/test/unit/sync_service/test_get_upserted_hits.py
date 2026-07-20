from datetime import timedelta


def test_no_interval_gets_all_hits():
    from sync.services import sync_service

    hits = sync_service.get_upserted_hits()["items"]
    assert len(hits) == 20


def test_interval_start_get_hits(current_time):
    from sync.services import sync_service

    start_time = current_time - timedelta(days=1)
    hits = sync_service.get_upserted_hits(data_interval_start=start_time)["items"]
    assert len(hits) == 10


def test_interval_start_with_updates(current_time):
    from sync.services import sync_service

    start_time = current_time - timedelta(days=2)
    hits = sync_service.get_upserted_hits(data_interval_start=start_time)["items"]
    assert len(hits) == 17  # 15 hits created in the last 2 days + 10 hits updated in the last 2 days - overlap


def test_interval_start_and_end_get_hits(current_time):
    from sync.services import sync_service

    start_time = current_time - timedelta(days=3)
    end_time = current_time - timedelta(days=2, hours=1)
    hits = sync_service.get_upserted_hits(data_interval_start=start_time, data_interval_end=end_time)["items"]
    assert len(hits) == 5


def test_interval_start_and_end_lower_bound_is_inclusive(current_time):
    from sync.services import sync_service

    start_time = current_time - timedelta(days=1)
    end_time = current_time
    hits = sync_service.get_upserted_hits(data_interval_start=start_time, data_interval_end=end_time)["items"]
    assert len(hits) == 10
