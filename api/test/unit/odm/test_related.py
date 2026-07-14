from howler.odm.models.ecs.related import Related
from howler.odm.models.hit import Hit


class TestRelated:
    def test_related_id_is_copied_to_ids(self):
        related = Related({"id": "indicator-1"})

        assert related.id == "indicator-1"
        assert related.ids == ["indicator-1"]

    def test_related_id_merges_into_existing_ids_without_duplicates(self):
        related = Related({"id": "indicator-2", "ids": ["indicator-1", "indicator-2"]})

        assert related.id == "indicator-2"
        assert related.ids == ["indicator-1", "indicator-2"]

    def test_related_id_merges_into_existing_ids_tuple(self):
        related = Related({"id": "indicator-2", "ids": ("indicator-1", "indicator-2")})

        assert related.id == "indicator-2"
        assert related.ids == ["indicator-1", "indicator-2"]

    def test_parent_odm_related_id_key_is_copied_to_related_ids(self):
        hit = Hit({"howler.analytic": "Test Analytic", "howler.hash": "a", "related.id": "indicator-3"})

        assert hit.related is not None
        assert hit.related.id == "indicator-3"
        assert hit.related.ids == ["indicator-3"]
