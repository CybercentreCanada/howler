"""Integration tests for the DatastoreMixin on the Hit model.

These tests exercise all aspects of the mixin API against a live Elasticsearch
instance: the Hit.store class-level descriptor, the hit.ds instance property,
and the hit.save() method.

Each test creates its own Hit instance (via generate_useful_hit), saves it
through the mixin, verifies persistence through the direct datastore_connection,
and cleans up afterwards.
"""

import pytest

from howler.common import loader
from howler.common.exceptions import HowlerRuntimeError
from howler.datastore.collection import ESCollection
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_hit
from howler.odm.models.hit import Hit

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    """Wire the loader singleton to the test datastore connection so that
    mixin calls to datastore() resolve to the same ES instance used for
    verification.  Any hits written by this module are wiped on teardown.
    """
    original = loader._datastore
    loader._datastore = datastore_connection

    yield datastore_connection

    # Restore the singleton; individual tests are responsible for deleting
    # their own documents, but this is a belt-and-suspenders cleanup.
    loader._datastore = original


@pytest.fixture(scope="module")
def lookups():
    return loader.get_lookups()


@pytest.fixture(scope="module")
def usernames(datastore: HowlerDatastore):
    return [user["uname"] for user in datastore.user.search("uname:*")["items"]]


def _make_hit(lookups, usernames) -> Hit:
    """Return a random, well-formed Hit ready to be saved."""
    return generate_useful_hit(lookups, usernames, prune_hit=False)


# ---------------------------------------------------------------------------
# Hit.store – class-level descriptor
# ---------------------------------------------------------------------------


class TestStoreDescriptor:
    """Integration tests for the Hit.store class-level descriptor."""

    def test_store_returns_es_collection(self, datastore):
        """Hit.store returns an ESCollection bound to the live datastore."""
        assert isinstance(Hit.store, ESCollection)

    def test_store_name_contains_hit(self, datastore):
        """Hit.store collection name is derived from the 'hit' index."""
        assert "hit" in Hit.store.name

    def test_store_can_search_hit_index(self, datastore):
        """Hit.store.search() runs against the live Elasticsearch instance."""
        result = Hit.store.search("howler.id:*", rows=0)
        assert "total" in result
        assert isinstance(result["total"], int)

    def test_store_raises_on_instance_access(self, lookups, usernames):
        """Accessing .store on a Hit instance raises AttributeError."""
        hit = _make_hit(lookups, usernames)
        with pytest.raises(HowlerRuntimeError) as exc_info:
            _ = hit.store
        assert "class-level" in str(exc_info.value)

    def test_store_error_message_includes_class_name(self, lookups, usernames):
        """AttributeError message from instance access mentions 'Hit'."""
        hit = _make_hit(lookups, usernames)
        with pytest.raises(HowlerRuntimeError) as exc_info:
            _ = hit.store
        assert "Hit" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Hit.ds – instance property
# ---------------------------------------------------------------------------


class TestDsProperty:
    """Integration tests for the hit.ds instance property."""

    def test_ds_returns_howler_datastore(self, datastore, lookups, usernames):
        """hit.ds returns a HowlerDatastore instance."""
        hit = _make_hit(lookups, usernames)
        assert isinstance(hit.ds, HowlerDatastore)

    def test_ds_returns_connected_datastore(self, datastore, lookups, usernames):
        """The datastore returned by hit.ds can reach Elasticsearch."""
        hit = _make_hit(lookups, usernames)
        result = hit.ds["hit"].search("howler.id:*", rows=0)
        assert "total" in result

    def test_ds_is_same_instance_as_loader(self, datastore, lookups, usernames):
        """hit.ds returns the same object as loader.datastore()."""
        hit = _make_hit(lookups, usernames)
        assert hit.ds is loader.datastore()

    def test_ds_accessible_from_multiple_instances(self, datastore, lookups, usernames):
        """Multiple distinct Hit instances each expose a live ds property."""
        hit_a = _make_hit(lookups, usernames)
        hit_b = _make_hit(lookups, usernames)
        assert isinstance(hit_a.ds, HowlerDatastore)
        assert isinstance(hit_b.ds, HowlerDatastore)


# ---------------------------------------------------------------------------
# Hit.save() – instance save method
# ---------------------------------------------------------------------------


class TestSaveMethod:
    """Integration tests for the hit.save() instance method."""

    def test_save_returns_true_on_success(self, datastore, lookups, usernames):
        """save() returns True when the hit is successfully persisted."""
        hit = _make_hit(lookups, usernames)
        hit_id = hit.howler.id
        try:
            result = hit.save()
            datastore.hit.commit()
            assert result is True
        finally:
            datastore.hit.delete(hit_id)

    def test_save_persists_hit_to_datastore(self, datastore, lookups, usernames):
        """After save(), the hit exists in the datastore."""
        hit = _make_hit(lookups, usernames)
        hit_id = hit.howler.id
        try:
            hit.save()
            datastore.hit.commit()
            assert datastore.hit.exists(hit_id)
        finally:
            datastore.hit.delete(hit_id)

    def test_save_preserves_hit_id_and_analytic(self, datastore, lookups, usernames):
        """The document retrieved after save() has the expected howler.id and analytic."""
        hit = _make_hit(lookups, usernames)
        hit_id = hit.howler.id
        analytic = hit.howler.analytic
        try:
            hit.save()
            datastore.hit.commit()
            retrieved = datastore.hit.get(hit_id)
            assert retrieved is not None
            assert retrieved.howler.id == hit_id
            assert retrieved.howler.analytic == analytic
        finally:
            datastore.hit.delete(hit_id)

    def test_save_uses_dotted_id_field(self, datastore, lookups, usernames):
        """save() derives the document key from the dotted 'howler.id' id_field."""
        hit = _make_hit(lookups, usernames)
        expected_id = hit.howler.id
        try:
            hit.save()
            datastore.hit.commit()
            # Verify the document was indexed under the exact ID from the dotted path.
            assert datastore.hit.exists(expected_id)
        finally:
            datastore.hit.delete(expected_id)

    def test_save_overwrites_existing_hit(self, datastore, lookups, usernames):
        """Calling save() twice on the same ID updates the stored document."""
        hit = _make_hit(lookups, usernames)
        hit_id = hit.howler.id
        try:
            hit.save()
            datastore.hit.commit()

            updated_analytic = f"{hit.howler.analytic}-updated"
            hit.howler.analytic = updated_analytic
            hit.save()
            datastore.hit.commit()

            retrieved = datastore.hit.get(hit_id)
            assert retrieved is not None
            assert retrieved.howler.analytic == updated_analytic
        finally:
            datastore.hit.delete(hit_id)

    def test_save_multiple_distinct_hits(self, datastore, lookups, usernames):
        """Multiple hits saved via the mixin are each individually retrievable."""
        hits = [_make_hit(lookups, usernames) for _ in range(3)]
        hit_ids = [h.howler.id for h in hits]
        try:
            for h in hits:
                h.save()
            datastore.hit.commit()
            for hit_id in hit_ids:
                assert datastore.hit.exists(hit_id)
        finally:
            for hit_id in hit_ids:
                datastore.hit.delete(hit_id)

    def test_save_via_store_and_save_are_consistent(self, datastore, lookups, usernames):
        """A hit saved via hit.save() is also visible through Hit.store.search()."""
        hit = _make_hit(lookups, usernames)
        hit_id = hit.howler.id
        try:
            hit.save()
            datastore.hit.commit()
            result = Hit.store.search(f"howler.id:{hit_id}", rows=1)
            assert result["total"] == 1
        finally:
            datastore.hit.delete(hit_id)
