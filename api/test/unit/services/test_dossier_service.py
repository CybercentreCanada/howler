from unittest.mock import MagicMock

import pytest

from howler.common.exceptions import InvalidDataException
from howler.models import Keyword
from howler.models.dossier import Dossier
from howler.models.user import User
from howler.services import dossier_service


def test_dossier_extension_survives_permitted_update(monkeypatch):
    class ExtendedDossier(Dossier):
        plugin: Keyword

    ds = MagicMock()
    ds.dossier.model_class = ExtendedDossier
    monkeypatch.setattr(dossier_service, "datastore", lambda: ds)
    owner = User.model_validate({"uname": "analyst", "name": "Analyst", "password": "hash"})
    created = dossier_service.create_dossier(
        {"title": "Investigation", "query": "howler.id:*", "type": "personal", "plugin": "keep"}, owner.uname
    )
    assert isinstance(created, ExtendedDossier)
    ds.dossier.save.assert_called_once_with(created.dossier_id, created, refresh=None)
    ds.dossier.exists.return_value = True
    ds.dossier.get_if_exists.return_value = created, "v1"

    with pytest.raises(InvalidDataException, match="can be updated"):
        dossier_service.update_dossier(created.dossier_id, {"plugin": "change"}, owner)
    updated = dossier_service.update_dossier(created.dossier_id, {"title": "Renamed"}, owner)
    assert updated.title == "Renamed"
    assert updated.as_primitives()["plugin"] == "keep"
    ds.dossier.save.assert_called_with(created.dossier_id, updated, version="v1", refresh=None)
