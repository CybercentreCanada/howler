"""Unit tests for the ingest API endpoint (howler.api.v2.ingest)."""

import uuid
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.common.loader import datastore
from howler.odm import Model
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


def _build_user(user_type: list[str] | None = None) -> User:
    user_data: User = random_model_obj(cast(Model, User))
    user_data.type = user_type or ["admin", "user"]
    user_data.uname = f"test_{uuid.uuid4().hex[:12]}"
    user_data.api_quota = 1000
    return user_data


def _mock_auth(mock_auth_service, user, priv=None):
    """Configure auth mocks so api_login passes."""
    if priv is None:
        priv = ["R", "W", "E"]
    mock_auth_service.bearer_auth = MagicMock(return_value=(user, priv))
    datastore().user.save(user.uname, user)


def _sample_hit(analytic: str = "Test Analytic", detection: str = "Test Detection") -> dict:
    return {
        "howler": {
            "analytic": analytic,
            "detection": detection,
        },
        "event": {
            "kind": "alert",
        },
    }


def _sample_observable() -> dict:
    return {
        "howler": {
            "data": ["raw entry"],
        },
    }


# ---------------------------------------------------------------------------
# POST /api/v2/ingest/<index> — create
# ---------------------------------------------------------------------------


class TestCreateEndpoint:
    """Tests for the POST create endpoint."""

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.observable_service")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_hit_success(
        self, mock_auth_service, mock_hit_svc, mock_obs_svc, mock_queue_fn, request_context: Flask
    ):
        """Returns 201 with IDs when hits are created successfully."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_hit = MagicMock()
        mock_hit.howler.id = "hit-001"
        mock_hit_svc.convert_hit.return_value = (mock_hit, [])

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit()],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit")

            assert result.status_code == 201
            body = result.get_json()
            assert body["api_response"] == ["hit-001"]
            mock_hit_svc.create_hit.assert_called_once()
            mock_queue_fn.return_value.push.assert_called_once_with("hit-001")

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.observable_service")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_observable_success(
        self, mock_auth_service, mock_hit_svc, mock_obs_svc, mock_queue_fn, request_context: Flask
    ):
        """Returns 201 with IDs when observables are created successfully."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_obs = MagicMock()
        mock_obs.howler.id = "obs-001"
        mock_obs_svc.convert_observable.return_value = (mock_obs, [])

        with request_context.test_request_context(
            method="POST",
            json=[_sample_observable()],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="observable")

            assert result.status_code == 201
            body = result.get_json()
            assert body["api_response"] == ["obs-001"]
            mock_obs_svc.create_observable.assert_called_once()
            mock_hit_svc.convert_hit.assert_not_called()

    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_no_body_returns_400(self, mock_auth_service, mock_hit_svc, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="POST",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit")

            assert result.status_code == 400

    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_non_list_returns_400(self, mock_auth_service, mock_hit_svc, request_context: Flask):
        """Returns 400 when the JSON payload is not a list."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="POST",
            json={"howler": {"analytic": "A"}},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit")

            assert result.status_code == 400

    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_multi_index_returns_400(self, mock_auth_service, mock_hit_svc, request_context: Flask):
        """Returns 400 when trying to create across multiple indexes."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit()],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit,observable")

            assert result.status_code == 400

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_multiple_hits(self, mock_auth_service, mock_hit_svc, mock_queue_fn, request_context: Flask):
        """Returns 201 with multiple IDs when multiple hits are created."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        hit1, hit2 = MagicMock(), MagicMock()
        hit1.howler.id = "hit-001"
        hit2.howler.id = "hit-002"
        mock_hit_svc.convert_hit.side_effect = [(hit1, []), (hit2, ["warning1"])]

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit(), _sample_hit(analytic="Other")],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit")

            assert result.status_code == 201
            body = result.get_json()
            assert body["api_response"] == ["hit-001", "hit-002"]
            assert "warning1" in body["api_warning"]
            mock_queue_fn.return_value.push.assert_called_once_with("hit-001", "hit-002")

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_conversion_failure_returns_400(
        self, mock_auth_service, mock_hit_svc, mock_queue_fn, request_context: Flask
    ):
        """Returns 400 when hit conversion raises HowlerException."""
        from howler.common.exceptions import HowlerValueError

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_hit_svc.convert_hit.side_effect = HowlerValueError("Invalid field")

        with request_context.test_request_context(
            method="POST",
            json=[{"bad": "data"}],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit")

            assert result.status_code == 400
            mock_queue_fn.return_value.push.assert_not_called()

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_create_queue_failure_still_returns_201(
        self, mock_auth_service, mock_hit_svc, mock_queue_fn, request_context: Flask
    ):
        """Returns 201 even when enqueuing to correlation queue fails."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_hit = MagicMock()
        mock_hit.howler.id = "hit-001"
        mock_hit_svc.convert_hit.return_value = (mock_hit, [])
        mock_queue_fn.return_value.push.side_effect = Exception("Redis down")

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit()],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            result: Response = create(index="hit")

            assert result.status_code == 201


# ---------------------------------------------------------------------------
# DELETE /api/v2/ingest/<indexes> — delete
# ---------------------------------------------------------------------------


class TestDeleteEndpoint:
    """Tests for the DELETE endpoint."""

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_delete_success_admin(self, mock_auth_service, mock_datastore, request_context: Flask):
        """Admin user can delete records and gets 204."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds
        mock_ds.__getitem__ = MagicMock(return_value=MagicMock())
        mock_ds.__getitem__.return_value.exists.return_value = True

        with request_context.test_request_context(
            method="DELETE",
            json=["hit-001"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import delete

            result: Response = delete(indexes="hit", user=user)

            assert result.status_code == 204

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_delete_no_body_returns_400(self, mock_auth_service, mock_datastore, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="DELETE",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import delete

            result: Response = delete(indexes="hit", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_delete_forbidden_non_admin(self, mock_auth_service, mock_datastore, request_context: Flask):
        """Non-admin user gets 403."""
        user = _build_user(["user"])
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="DELETE",
            json=["hit-001"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import delete

            result: Response = delete(indexes="hit", user=user)

            assert result.status_code == 403

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_delete_not_found_returns_404(self, mock_auth_service, mock_datastore, request_context: Flask):
        """Returns 404 when record IDs do not exist."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds
        mock_ds.__getitem__ = MagicMock(return_value=MagicMock())
        mock_ds.__getitem__.return_value.exists.return_value = False

        with request_context.test_request_context(
            method="DELETE",
            json=["nonexistent"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import delete

            result: Response = delete(indexes="hit", user=user)

            assert result.status_code == 404

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_delete_across_multiple_indexes(self, mock_auth_service, mock_datastore, request_context: Flask):
        """Deletion across comma-separated indexes returns 204."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds
        mock_index = MagicMock()
        mock_index.exists.return_value = True
        mock_ds.__getitem__ = MagicMock(return_value=mock_index)

        with request_context.test_request_context(
            method="DELETE",
            json=["rec-001"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import delete

            result: Response = delete(indexes="hit,observable", user=user)

            assert result.status_code == 204

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_delete_datastore_error_returns_500(self, mock_auth_service, mock_datastore, request_context: Flask):
        """Returns 500 when the datastore raises an error during deletion."""
        from howler.datastore.exceptions import DataStoreException

        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds
        mock_index = MagicMock()
        mock_index.exists.return_value = True
        mock_index.delete.side_effect = DataStoreException("ES failure")
        mock_ds.__getitem__ = MagicMock(return_value=mock_index)

        with request_context.test_request_context(
            method="DELETE",
            json=["hit-001"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import delete

            result: Response = delete(indexes="hit", user=user)

            assert result.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/v2/ingest/<index>/validate — validate
# ---------------------------------------------------------------------------


class TestValidateEndpoint:
    """Tests for the POST validate endpoint."""

    @patch("howler.api.v2.ingest.hit_service")
    def test_validate_valid_hits(self, mock_hit_svc, request_context: Flask):
        """Valid hits are placed in the 'valid' list."""
        mock_hit_svc.convert_hit.return_value = (MagicMock(), [])

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit()],
            headers={"Content-Type": "application/json"},
        ):
            from howler.api.v2.ingest import validate

            result: Response = validate(index="hit")

            assert result.status_code == 200
            body = result.get_json()
            assert len(body["api_response"]["valid"]) == 1
            assert len(body["api_response"]["invalid"]) == 0

    @patch("howler.api.v2.ingest.hit_service")
    def test_validate_invalid_hit(self, mock_hit_svc, request_context: Flask):
        """Invalid hits are placed in the 'invalid' list with the error message."""
        from howler.common.exceptions import HowlerValueError

        mock_hit_svc.convert_hit.side_effect = HowlerValueError("Bad field")

        with request_context.test_request_context(
            method="POST",
            json=[{"bad": "data"}],
            headers={"Content-Type": "application/json"},
        ):
            from howler.api.v2.ingest import validate

            result: Response = validate(index="hit")

            assert result.status_code == 200
            body = result.get_json()
            assert len(body["api_response"]["valid"]) == 0
            assert len(body["api_response"]["invalid"]) == 1
            assert "Bad field" in body["api_response"]["invalid"][0]["error"]

    @patch("howler.api.v2.ingest.observable_service")
    def test_validate_observable(self, mock_obs_svc, request_context: Flask):
        """Observable index routes to convert_observable."""
        mock_obs_svc.convert_observable.return_value = (MagicMock(), [])

        with request_context.test_request_context(
            method="POST",
            json=[_sample_observable()],
            headers={"Content-Type": "application/json"},
        ):
            from howler.api.v2.ingest import validate

            result: Response = validate(index="observable")

            assert result.status_code == 200
            body = result.get_json()
            assert len(body["api_response"]["valid"]) == 1

    def test_validate_no_body_returns_400(self, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        with request_context.test_request_context(
            method="POST",
            data=b"null",
            content_type="application/json",
        ):
            from howler.api.v2.ingest import validate

            result: Response = validate(index="hit")

            assert result.status_code == 400

    def test_validate_multi_index_returns_400(self, request_context: Flask):
        """Returns 400 when trying to validate across multiple indexes."""
        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit()],
            headers={"Content-Type": "application/json"},
        ):
            from howler.api.v2.ingest import validate

            result: Response = validate(index="hit,observable")

            assert result.status_code == 400

    @patch("howler.api.v2.ingest.hit_service")
    def test_validate_mixed_valid_and_invalid(self, mock_hit_svc, request_context: Flask):
        """A batch with both valid and invalid hits returns both lists correctly."""
        from howler.common.exceptions import HowlerValueError

        mock_hit_svc.convert_hit.side_effect = [
            (MagicMock(), []),
            HowlerValueError("Missing field"),
        ]

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit(), {"bad": "data"}],
            headers={"Content-Type": "application/json"},
        ):
            from howler.api.v2.ingest import validate

            result: Response = validate(index="hit")

            assert result.status_code == 200
            body = result.get_json()
            assert len(body["api_response"]["valid"]) == 1
            assert len(body["api_response"]["invalid"]) == 1


# ---------------------------------------------------------------------------
# POST /api/v2/ingest/<index> — enqueue for correlation
# ---------------------------------------------------------------------------


class TestIngestionQueueing:
    """Tests that the create endpoint enqueues IDs for the correlation worker."""

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_enqueues_hit_ids(self, mock_auth_service, mock_hit_svc, mock_queue_fn, request_context: Flask):
        """All newly created hit IDs are pushed to the ingestion queue."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        hit1, hit2 = MagicMock(), MagicMock()
        hit1.howler.id = "hit-a"
        hit2.howler.id = "hit-b"
        mock_hit_svc.convert_hit.side_effect = [(hit1, []), (hit2, [])]

        with request_context.test_request_context(
            method="POST",
            json=[_sample_hit(), _sample_hit()],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            create(index="hit")

            mock_queue_fn.return_value.push.assert_called_once_with("hit-a", "hit-b")

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.observable_service")
    @patch("howler.security.auth_service")
    def test_enqueues_observable_ids(self, mock_auth_service, mock_obs_svc, mock_queue_fn, request_context: Flask):
        """Observable IDs are also enqueued for correlation."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        obs = MagicMock()
        obs.howler.id = "obs-a"
        mock_obs_svc.convert_observable.return_value = (obs, [])

        with request_context.test_request_context(
            method="POST",
            json=[_sample_observable()],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            create(index="observable")

            mock_queue_fn.return_value.push.assert_called_once_with("obs-a")

    @patch("howler.api.v2.ingest._get_ingestion_queue")
    @patch("howler.api.v2.ingest.hit_service")
    @patch("howler.security.auth_service")
    def test_no_enqueue_when_all_fail(self, mock_auth_service, mock_hit_svc, mock_queue_fn, request_context: Flask):
        """Queue push is not called when every record fails conversion."""
        from howler.common.exceptions import HowlerValueError

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_hit_svc.convert_hit.side_effect = HowlerValueError("bad")

        with request_context.test_request_context(
            method="POST",
            json=[{"bad": "data"}],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import create

            create(index="hit")

            mock_queue_fn.return_value.push.assert_not_called()


# ---------------------------------------------------------------------------
# PATCH /api/v2/ingest/<index>/<id>/overwrite
# ---------------------------------------------------------------------------


class TestOverwrite:
    """Tests for the overwrite endpoint."""

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_overwrite_success(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 200 with the updated record on successful overwrite."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        existing = {"howler": {"id": "hit-001", "analytic": "A"}, "event": {"kind": "alert"}}
        mock_ds.return_value.__getitem__.return_value.get.side_effect = [
            existing,
            ({"howler": {"id": "hit-001", "analytic": "B"}, "event": {"kind": "alert"}}, "v2"),
        ]
        mock_ds.return_value.__getitem__.return_value.save.return_value = True

        with request_context.test_request_context(
            method="PATCH",
            json={"howler": {"analytic": "B"}},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import overwrite

            result: Response = overwrite(index="hit", id="hit-001", server_version="v1", user=user)[0]

            assert result.status_code == 200

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_overwrite_multi_index_returns_400(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 400 when index contains a comma."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PATCH",
            json={"howler": {"analytic": "B"}},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import overwrite

            result: Response = overwrite(index="hit,observable", id="hit-001", server_version="v1", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_overwrite_not_found(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 404 when the record does not exist."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_ds.return_value.__getitem__.return_value.get.return_value = None

        with request_context.test_request_context(
            method="PATCH",
            json={"howler": {"analytic": "B"}},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import overwrite

            result: Response = overwrite(index="hit", id="hit-001", server_version="v1", user=user)

            assert result.status_code == 404

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_overwrite_non_dict_body_returns_400(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 400 when the JSON payload is not a dict."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_ds.return_value.__getitem__.return_value.get.return_value = {"howler": {"id": "hit-001"}}

        with request_context.test_request_context(
            method="PATCH",
            json=["not", "a", "dict"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import overwrite

            result: Response = overwrite(index="hit", id="hit-001", server_version="v1", user=user)

            assert result.status_code == 400


# ---------------------------------------------------------------------------
# PUT /api/v2/ingest/<indexes>/update
# ---------------------------------------------------------------------------


class TestUpdateByQuery:
    """Tests for the update_by_query endpoint."""

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_update_by_query_success(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 200 with success=True on valid update."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_ds.return_value.__getitem__.return_value.update_by_query.return_value = True

        with request_context.test_request_context(
            method="PUT",
            json={
                "query": "howler.id:*",
                "operations": [["SET", "howler.assignment", "user"]],
            },
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import update_by_query

            result: Response = update_by_query(indexes="hit", user=user)

            assert result.status_code == 200
            body = result.get_json()
            assert body["api_response"]["success"] is True

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_update_by_query_bad_operation_returns_400(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 400 when an operation fails validation."""

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PUT",
            json={
                "query": "howler.id:*",
                "operations": [["INVALID_OP", "howler.assignment", "user"]],
            },
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import update_by_query

            result: Response = update_by_query(indexes="hit", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.ingest.datastore")
    @patch("howler.security.auth_service")
    def test_update_by_query_missing_query_returns_400(self, mock_auth_service, mock_ds, request_context: Flask):
        """Returns 400 when the query key is missing from the body."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PUT",
            json={
                "operations": [["SET", "howler.assignment", "user"]],
            },
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.ingest import update_by_query

            result: Response = update_by_query(indexes="hit", user=user)

            assert result.status_code == 400
