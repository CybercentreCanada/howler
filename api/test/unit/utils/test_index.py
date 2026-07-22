import pytest

from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.datastore.exceptions import SearchException
from howler.utils import indexes
from howler.utils.indexes import get_logical_index_name, normalize_indexes


class TestNormalizeIndexes:
    def test_normalize_indexes_string(self):
        assert normalize_indexes("user,hit") == f"{DATASTORE_INDEX_PREFIX}-user,{DATASTORE_INDEX_PREFIX}-hit"

    def test_normalize_indexes_list_and_special_values(self):
        assert normalize_indexes(["*", "_all", "custom-index", "event*"]) == "*,_all,custom-index,event*"

    @pytest.mark.parametrize("indexes", ["", " , ", [], [" "]])
    def test_normalize_indexes_fails_on_empty(self, indexes):
        with pytest.raises(SearchException, match="No indexes were provided"):
            normalize_indexes(indexes)

    def test_single_index_adds_prefix_and_suffix(self):
        """A plain index name gets the datastore index prefix."""
        result = normalize_indexes("hit")

        assert result == f"{DATASTORE_INDEX_PREFIX}-hit"

    def test_multiple_indexes_comma_separated(self):
        """Comma-separated indexes are each normalized."""
        result = normalize_indexes("hit,event")

        parts = result.split(",")
        assert len(parts) == 2
        assert parts[0] == f"{DATASTORE_INDEX_PREFIX}-hit"
        assert parts[1] == f"{DATASTORE_INDEX_PREFIX}-event"

    def test_wildcard_preserved(self):
        """Wildcard '*' is kept as-is."""
        result = normalize_indexes("*")

        assert result == "*"

    def test_exclusion_pattern_preserved(self):
        """Indexes with a dash (exclusion pattern) are kept as-is."""
        result = normalize_indexes("custom-index")

        assert result == "custom-index"

    def test_list_input(self):
        """A list of indexes is handled correctly."""
        result = normalize_indexes(["hit", "event"])

        parts = result.split(",")
        assert len(parts) == 2
        assert all(p.startswith(DATASTORE_INDEX_PREFIX) for p in parts)

    def test_empty_string_raises(self):
        """An empty string raises SearchException."""
        with pytest.raises(SearchException):
            normalize_indexes("")

    def test_empty_list_raises(self):
        """An empty list raises SearchException."""
        with pytest.raises(SearchException):
            normalize_indexes([])

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace in index names is stripped."""
        result = normalize_indexes("  hit , event  ")

        parts = result.split(",")
        assert len(parts) == 2
        assert all(p.startswith(DATASTORE_INDEX_PREFIX) for p in parts)

    def test_all_keyword_preserved(self):
        """The '_all' keyword is preserved as-is."""
        result = normalize_indexes("_all")

        assert result == "_all"

    def test_mixed_wildcard_and_plain(self):
        """Mix of wildcards and plain indexes normalizes correctly."""
        result = normalize_indexes("*,hit")

        parts = result.split(",")
        assert parts[0] == "*"
        assert parts[1] == f"{DATASTORE_INDEX_PREFIX}-hit"


class TestGetLogicalIndexName:
    @pytest.mark.parametrize(
        ("raw_index", "expected"),
        [
            (f"{DATASTORE_INDEX_PREFIX}-alerts", "alerts"),
            (f"{DATASTORE_INDEX_PREFIX}-alerts_hot", "alerts"),
            (f"{DATASTORE_INDEX_PREFIX}-alerts-000001", "alerts"),
            (f"{DATASTORE_INDEX_PREFIX}-alerts_hot-000001", "alerts"),
            ("external-alerts_hot-000001", "external-alerts"),
            ("alerts_hot", "alerts"),
            ("alerts-000001", "alerts"),
            ("alerts-2024-events", "alerts-2024-events"),
        ],
    )
    def test_strips_physical_name_components(self, raw_index, expected):
        assert get_logical_index_name(raw_index) == expected

    def test_uses_application_name_when_datastore_prefix_differs(self, monkeypatch):
        monkeypatch.setattr(indexes, "DATASTORE_INDEX_PREFIX", "datastore")
        monkeypatch.setattr(indexes, "APP_NAME", "howler")

        assert indexes.get_logical_index_name("howler-alerts_hot-000001") == "alerts"

    def test_prefers_the_longest_matching_prefix(self, monkeypatch):
        monkeypatch.setattr(indexes, "DATASTORE_INDEX_PREFIX", "howler-development")
        monkeypatch.setattr(indexes, "APP_NAME", "howler")

        assert indexes.get_logical_index_name("howler-development-alerts_hot-000001") == "alerts"
