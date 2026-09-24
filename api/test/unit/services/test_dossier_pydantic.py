"""Dossier CRUD accepts finalized Pydantic models and persisted primitives."""

from unittest.mock import MagicMock, patch

from howler.models.dossier import Dossier
from howler.models.user import User
from howler.services import dossier_service


def test_create_and_update_dossier_use_pydantic_models():
    storage = MagicMock()
    dossier_data = {"title": "Investigation", "query": "howler.id:*", "type": "personal"}
    requester = User.validate_howler({"uname": "analyst", "name": "Analyst", "password": "hash"})

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
