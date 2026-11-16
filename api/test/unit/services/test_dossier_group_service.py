from unittest.mock import MagicMock, patch

from howler.models.dossier import Dossier
from howler.models.user import User
from howler.services import dossier_service


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_filters_prefix_deduplicates_sorts_and_caps(mock_datastore):
    matching_groups = [f"network/alpha-{index:02}" for index in range(dossier_service.MAX_GROUP_SUGGESTIONS + 2)]
    mock_datastore.return_value.dossier.search.return_value = {
        "aggregations": {
            "pivot_groups": {
                "groups": {
                    "buckets": [
                        *({"key": {"group": group}} for group in matching_groups),
                        {"key": {"group": "network/dns"}},
                        {"key": {"group": "Network/DHCP"}},
                        {"key": {"group": "identity/user"}},
                    ]
                }
            }
        }
    }

    results = dossier_service.get_pivot_groups("NETWORK/", username="analyst")

    expected_groups = sorted({"network/dns", "Network/DHCP", *matching_groups})[: dossier_service.MAX_GROUP_SUGGESTIONS]
    assert results == expected_groups
    assert len(results) == dossier_service.MAX_GROUP_SUGGESTIONS


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_scopes_search_to_visible_dossiers(mock_datastore):
    mock_datastore.return_value.dossier.search.return_value = {
        "aggregations": {"pivot_groups": {"groups": {"buckets": []}}}
    }

    dossier_service.get_pivot_groups("network", username="analyst")

    mock_datastore.return_value.dossier.search.assert_called_once_with(
        '(type:global OR owner:("analyst" OR none))',
        rows=0,
        aggregations=[
            (
                "pivot_groups",
                {
                    "filter": {
                        "prefix": {
                            "pivots.group": {
                                "value": "network",
                                "case_insensitive": True,
                            }
                        }
                    },
                    "aggs": {
                        "groups": {
                            "composite": {
                                "size": dossier_service.GROUP_SUGGESTION_PAGE_SIZE,
                                "sources": [{"group": {"terms": {"field": "pivots.group"}}}],
                            }
                        }
                    },
                },
            )
        ],
    )


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_escapes_username_in_visibility_query(mock_datastore):
    mock_datastore.return_value.dossier.search.return_value = {
        "aggregations": {"pivot_groups": {"groups": {"buckets": []}}}
    }

    dossier_service.get_pivot_groups("network", username="analyst) OR owner:(other")

    mock_datastore.return_value.dossier.search.assert_called_once_with(
        '(type:global OR owner:("analyst\\) OR owner\\:\\(other" OR none))',
        rows=0,
        aggregations=[
            (
                "pivot_groups",
                {
                    "filter": {
                        "prefix": {
                            "pivots.group": {
                                "value": "network",
                                "case_insensitive": True,
                            }
                        }
                    },
                    "aggs": {
                        "groups": {
                            "composite": {
                                "size": dossier_service.GROUP_SUGGESTION_PAGE_SIZE,
                                "sources": [{"group": {"terms": {"field": "pivots.group"}}}],
                            }
                        }
                    },
                },
            )
        ],
    )


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_handles_missing_pivots(mock_datastore):
    mock_datastore.return_value.dossier.search.return_value = {
        "aggregations": {"pivot_groups": {"groups": {"buckets": [{"key": {"group": "network/dns"}}]}}}
    }

    assert dossier_service.get_pivot_groups("", username="analyst") == ["network/dns"]


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_pages_before_capping(mock_datastore):
    mock_datastore.return_value.dossier.search.side_effect = [
        {
            "aggregations": {
                "pivot_groups": {
                    "groups": {
                        "buckets": [{"key": {"group": "network/zulu"}}],
                        "after_key": {"group": "network/zulu"},
                    }
                }
            }
        },
        {
            "aggregations": {
                "pivot_groups": {
                    "groups": {"buckets": [{"key": {"group": "network/alpha"}}, {"key": {"group": "Network/Beta"}}]}
                }
            }
        },
    ]

    assert dossier_service.get_pivot_groups("network/", username="analyst") == [
        "Network/Beta",
        "network/alpha",
        "network/zulu",
    ]
    assert mock_datastore.return_value.dossier.search.call_count == 2
    assert mock_datastore.return_value.dossier.search.call_args_list[1].kwargs["aggregations"][0][1]["aggs"]["groups"][
        "composite"
    ]["after"] == {"group": "network/zulu"}


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_stops_after_the_page_limit(mock_datastore):
    mock_datastore.return_value.dossier.search.side_effect = [
        {
            "aggregations": {
                "pivot_groups": {
                    "groups": {
                        "buckets": [{"key": {"group": f"network/page{page:02}"}}],
                        "after_key": {"group": f"network/page{page:02}"},
                    }
                }
            }
        }
        for page in range(dossier_service.MAX_GROUP_SUGGESTION_PAGES + 1)
    ]

    assert dossier_service.get_pivot_groups("network/", username="analyst") == [
        f"network/page{page:02}" for page in range(dossier_service.MAX_GROUP_SUGGESTION_PAGES)
    ]
    assert mock_datastore.return_value.dossier.search.call_count == dossier_service.MAX_GROUP_SUGGESTION_PAGES


def test_create_and_update_dossier_persist_editable_fields():
    storage = MagicMock()
    requester = User.validate_howler({"uname": "analyst", "name": "Analyst", "password": "hash"})
    dossier_data = {"title": "Investigation", "query": "howler.id:*", "type": "personal"}

    with patch.object(dossier_service, "datastore", return_value=storage):
        created = dossier_service.create_dossier(dossier_data, "analyst")

    assert isinstance(created, Dossier)
    assert created.owner == "analyst"
    storage.dossier.save.assert_called_once_with(created.dossier_id, created, refresh=None)

    storage.dossier.exists.return_value = True
    storage.dossier.get_if_exists.return_value = created, "1---1"
    with patch.object(dossier_service, "datastore", return_value=storage):
        updated = dossier_service.update_dossier(created.dossier_id, {"title": "Updated"}, requester)

    assert isinstance(updated, Dossier)
    assert updated.title == "Updated"
    assert updated.owner == "analyst"
    storage.dossier.save.assert_called_with(created.dossier_id, updated, version="1---1", refresh=None)
