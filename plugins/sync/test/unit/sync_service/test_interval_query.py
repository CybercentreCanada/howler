from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from sync.services import sync_service


@pytest.mark.parametrize(
    ("start", "end", "expected_range"),
    [
        (None, None, "[* TO *]"),
        (datetime(2026, 1, 2, 3, 4, 5, 123456), None, "[2026-01-02T03:04:05.123456Z TO *]"),
        (None, datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc), "[* TO 2026-01-02T03:04:05.000000Z]"),
        (
            datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=2))),
            datetime(2026, 1, 3, 3, 4, 5, tzinfo=timezone(timedelta(hours=-3))),
            "[2026-01-02T01:04:05.000000Z TO 2026-01-03T06:04:05.000000Z]",
        ),
    ],
)
def test_get_upserted_hits_interval_query(monkeypatch, start, end, expected_range):
    storage = MagicMock()
    monkeypatch.setattr(sync_service, "datastore", lambda: storage)

    result = sync_service.get_upserted_hits(data_interval_start=start, data_interval_end=end)

    storage.hit.search.assert_called_once_with(
        query=f"timestamp:{expected_range} OR howler.log.timestamp:{expected_range}",
        deep_paging_id=None,
        offset=0,
        rows=None,
        timeout=None,
        as_obj=True,
    )
    assert result is storage.hit.search.return_value
