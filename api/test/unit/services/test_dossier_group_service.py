from types import SimpleNamespace
from unittest.mock import patch

from howler.services import dossier_service


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_filters_prefix_deduplicates_sorts_and_caps(mock_datastore):
    matching_groups = [f"network/alpha-{index:02}" for index in range(dossier_service.MAX_GROUP_SUGGESTIONS + 2)]
    visible_dossiers = [
        SimpleNamespace(
            pivots=[
                SimpleNamespace(group="network/dns"),
                SimpleNamespace(group="Network/DHCP"),
                SimpleNamespace(group="identity/user"),
                SimpleNamespace(group="network/dns"),
                SimpleNamespace(group=None),
            ]
        ),
        SimpleNamespace(pivots=[SimpleNamespace(group=group) for group in matching_groups]),
    ]
    mock_datastore.return_value.dossier.search.return_value = {"items": visible_dossiers}

    results = dossier_service.get_pivot_groups("NETWORK/", username="analyst")

    # scanning stops as soon as MAX_GROUP_SUGGESTIONS unique matches are found, so only the groups
    # encountered up to that point are included, not every matching group across all dossiers
    first_dossier_groups = ["network/dns", "Network/DHCP"]
    remaining_slots = dossier_service.MAX_GROUP_SUGGESTIONS - len(first_dossier_groups)
    expected_groups = sorted({*first_dossier_groups, *matching_groups[:remaining_slots]})
    assert results == expected_groups
    assert len(results) == dossier_service.MAX_GROUP_SUGGESTIONS


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_scopes_search_to_visible_dossiers(mock_datastore):
    mock_datastore.return_value.dossier.search.return_value = {"items": []}

    dossier_service.get_pivot_groups("network", username="analyst")

    mock_datastore.return_value.dossier.search.assert_called_once_with(
        "(type:global OR owner:(analyst OR none)) AND (pivots.group:*)",
        as_obj=True,
        rows=100,
        fl="pivots.group",
    )


@patch("howler.services.dossier_service.datastore")
def test_get_pivot_groups_handles_missing_pivots(mock_datastore):
    mock_datastore.return_value.dossier.search.return_value = {
        "items": [
            SimpleNamespace(pivots=[]),
            SimpleNamespace(pivots=[SimpleNamespace(group=None), SimpleNamespace(group="network/dns")]),
        ]
    }

    assert dossier_service.get_pivot_groups("", username="analyst") == ["network/dns"]
