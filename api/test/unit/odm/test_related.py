from howler.odm.models.ecs.related import Related


class TestRelated:
    def test_related_id_is_copied_to_ids(self):
        related = Related({"id": "indicator-1"})

        assert related.id == "indicator-1"
        assert related.ids == ["indicator-1"]

    def test_related_id_merges_into_existing_ids_without_duplicates(self):
        related = Related({"id": "indicator-2", "ids": ["indicator-1", "indicator-2"]})

        assert related.id == "indicator-2"
        assert related.ids == ["indicator-1", "indicator-2"]
