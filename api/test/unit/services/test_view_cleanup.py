from unittest.mock import MagicMock, patch

from howler.cronjobs import view_cleanup
from howler.models import construct_partial
from howler.models.user import User


def test_view_cleanup_keeps_valid_views_and_other_dashboard_entries_across_pages():
    def user(name, entries):
        return construct_partial(
            User,
            {
                "uname": name,
                "dashboard": [{"entry_id": entry, "type": kind, "config": "{}"} for entry, kind in entries],
            },
        )

    first = user("user-1", [("missing", "view"), ("analytic-1", "analytic")])
    second = user("user-2", [("valid", "view")])
    storage = MagicMock()
    storage.user.search.side_effect = [{"total": 2, "items": [u]} for u in (first, second)]
    storage.view.search.side_effect = [{"total": 2, "items": [MagicMock(view_id=v)]} for v in ("other", "valid")]

    with patch("howler.common.loader.datastore", return_value=storage):
        view_cleanup.execute()

    assert [entry.entry_id for entry in first.dashboard] == ["analytic-1"]
    assert [entry.entry_id for entry in second.dashboard] == ["valid"]
    storage.user.save.assert_called_once_with("user-1", first)
    assert storage.view.search.call_args_list[-1].kwargs["offset"] == 1
    assert storage.user.search.call_args_list[-1].kwargs["offset"] == 1
