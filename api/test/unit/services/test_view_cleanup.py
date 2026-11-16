from unittest.mock import MagicMock, patch

from howler.cronjobs import view_cleanup
from howler.models import construct_partial
from howler.models.user import User


def test_view_cleanup_removes_deleted_pinned_views():
    user = construct_partial(
        User,
        {
            "uname": "user-1",
            "dashboard": [{"entry_id": "deleted-view", "type": "view", "config": "{}"}],
        },
    )
    storage = MagicMock()
    storage.user.search.return_value = {"total": 1, "items": [user]}
    storage.view.search.return_value = {"total": 0, "items": []}

    with patch("howler.common.loader.datastore", return_value=storage):
        view_cleanup.execute()

    assert user.dashboard == []
    storage.user.save.assert_called_once_with("user-1", user)


def test_view_cleanup_keeps_valid_views_and_other_dashboard_entries_across_pages():
    first = construct_partial(
        User,
        {
            "uname": "user-1",
            "dashboard": [
                {"entry_id": "missing", "type": "view", "config": "{}"},
                {"entry_id": "analytic-1", "type": "analytic", "config": "{}"},
            ],
        },
    )
    second = construct_partial(
        User,
        {"uname": "user-2", "dashboard": [{"entry_id": "valid", "type": "view", "config": "{}"}]},
    )
    storage = MagicMock()
    storage.user.search.side_effect = [
        {"total": 2, "items": [first]},
        {"total": 2, "items": [second]},
    ]
    storage.view.search.side_effect = [
        {"total": 2, "items": [MagicMock(view_id="other")]},
        {"total": 2, "items": [MagicMock(view_id="valid")]},
    ]

    with patch("howler.common.loader.datastore", return_value=storage):
        view_cleanup.execute()

    assert [entry.entry_id for entry in first.dashboard] == ["analytic-1"]
    assert [entry.entry_id for entry in second.dashboard] == ["valid"]
    storage.user.save.assert_called_once_with("user-1", first)
    assert storage.view.search.call_args_list[-1].kwargs["offset"] == 1
    assert storage.user.search.call_args_list[-1].kwargs["offset"] == 1
