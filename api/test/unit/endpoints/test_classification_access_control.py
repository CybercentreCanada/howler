"""Unit tests for classification-based access control enforcement.

Covers the per-document classification checks added to endpoints covering the
access-controlled indexes (hit, event, case):

  - ``howler.security.utils.is_classification_accessible`` helper semantics
    (level comparison, admin bypass, missing classifications)
  - v2 case endpoints deny access with **generic 404s** so classified cases
    are indistinguishable from nonexistent ones
  - classification escalation via create/update payloads is rejected with 400
  - v1 hit creation and update-by-query enforce/propagate the user's
    access-control filter
  - deprecated bundle endpoints hide or drop hits the user cannot access

The real classification engine depends on the deployment's classification.yml,
so these tests stub ``howler.security.utils.CLASSIFICATION`` with a
deterministic two-level engine (UNRESTRICTED < RESTRICTED) to keep the
enforcement semantics independent of local configuration.
"""

import uuid
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.common.loader import datastore
from howler.odm import Model
from howler.odm.models.case import Case
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubClassificationEngine:
    """Deterministic two-level classification engine (UNRESTRICTED < RESTRICTED).

    Mirrors the parts of ``ClassificationEngine`` the ODM relies on when wrapping
    raw strings into ``ClassificationObject`` (identity normalization), and
    accepts both plain strings and wrapped objects in ``is_accessible``.
    """

    UNRESTRICTED = "UNRESTRICTED"
    RESTRICTED = "RESTRICTED"
    LEVELS = {"UNRESTRICTED": 100, "RESTRICTED": 200}
    enforce = True

    @classmethod
    def _val(cls, c12n):
        return getattr(c12n, "value", c12n)

    def normalize_classification(self, c12n, **kwargs):
        return self._val(c12n)

    def list_all_classification_combinations(self, long_format=True, normalized=False):
        return set(self.LEVELS)

    def get_access_control_parts(self, c12n=None, user_classification=False):
        value = self._val(c12n) if c12n is not None else self.UNRESTRICTED
        return {
            "__access_lvl__": self.LEVELS.get(value, self.LEVELS[self.UNRESTRICTED]),
            "__access_req__": [],
            "__access_grp1__": ["__EMPTY__"],
            "__access_grp2__": ["__EMPTY__"],
        }

    def is_accessible(self, user_c12n, c12n, ignore_invalid=False):
        if c12n is None:
            return True

        user_lvl = self.LEVELS.get(self._val(user_c12n))
        doc_lvl = self.LEVELS.get(self._val(c12n))
        if user_lvl is None or doc_lvl is None:
            return False

        return user_lvl >= doc_lvl


@pytest.fixture
def stub_classification(monkeypatch):
    """Replace the classification engine everywhere it gets used.

    Patches:
      - the security helper's engine
      - loader.get_classification (used by freshly constructed fields)
      - the engine already captured by the ``Classification`` fields on the
        User and Hit models, since those are bound at class-definition time
        and would otherwise normalize values against the deployment's
        classification.yml (which may be missing/invalid in CI).
    """
    import howler.common.loader as loader
    import howler.security.utils as security_utils
    from howler.odm.base import Classification
    from howler.odm.models.hit import Hit as HitModel

    engine = StubClassificationEngine()
    monkeypatch.setattr(security_utils, "CLASSIFICATION", engine)
    monkeypatch.setattr(loader, "get_classification", lambda yml_config=None: engine)

    for model in (User, HitModel):
        for field in model.flat_fields().values():
            if isinstance(field, Classification):
                monkeypatch.setattr(field, "engine", engine)

    return engine


def _build_user(
    user_type: list[str] | None = None,
    classification: str = "UNRESTRICTED",
) -> User:
    """Build a random valid user with a deterministic type and classification."""
    user: User = random_model_obj(cast(Model, User))
    user.type = user_type or ["user"]
    user.classification = classification
    user.uname = f"test_{uuid.uuid4().hex[:12]}"
    # The randomizer may draw a tiny/zero quota, which makes api_login reject
    # the request with a 429 before it reaches the endpoint.
    user.api_quota = 1000
    return user


def _mock_auth(mock_auth_service, user, priv=None):
    """Configure auth mocks so api_login passes."""
    if priv is None:
        priv = ["R", "W", "E"]
    mock_auth_service.bearer_auth = MagicMock(return_value=(user, priv))
    datastore().user.save(user.uname, user)


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


# ---------------------------------------------------------------------------
# is_classification_accessible helper
# ---------------------------------------------------------------------------


class TestValidateBulkOperationTargets:
    """Tests for the shared bulk-update field validator."""

    def test_allows_regular_fields(self):
        from howler.security.utils import validate_bulk_operation_targets

        validate_bulk_operation_targets([("SET", "howler.status", "open"), ("APPEND", "howler.labels.x", "y")])

    def test_rejects_protected_fields(self):
        import pytest

        from howler.common.exceptions import HowlerValueError
        from howler.security.utils import PROTECTED_UPDATE_FIELDS, validate_bulk_operation_targets

        for field in PROTECTED_UPDATE_FIELDS:
            with pytest.raises(HowlerValueError, match=f"protected field {field}"):
                validate_bulk_operation_targets([("SET", "howler.status", "open"), ("SET", field, 1)])


class TestIsClassificationAccessible:
    """Tests for the shared per-document classification check."""

    def test_admin_bypasses_access_control(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        admin = {"type": ["admin", "user"], "classification": "UNRESTRICTED"}
        assert is_classification_accessible(admin, "RESTRICTED") is True

    def test_user_can_access_at_own_level(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        user = {"type": ["user"], "classification": "RESTRICTED"}
        assert is_classification_accessible(user, "RESTRICTED") is True

    def test_user_can_access_below_own_level(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        user = {"type": ["user"], "classification": "RESTRICTED"}
        assert is_classification_accessible(user, "UNRESTRICTED") is True

    def test_denied_above_own_level(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        user = {"type": ["user"], "classification": "UNRESTRICTED"}
        assert is_classification_accessible(user, "RESTRICTED") is False

    def test_unclassified_document_is_accessible(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        user = {"type": ["user"], "classification": "UNRESTRICTED"}
        assert is_classification_accessible(user, None) is True

    def test_missing_user_classification_defaults_to_unrestricted(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        user = {"type": ["user"]}
        assert is_classification_accessible(user, "UNRESTRICTED") is True
        assert is_classification_accessible(user, "RESTRICTED") is False

    def test_accepts_user_odm_objects(self, stub_classification):
        from howler.security.utils import is_classification_accessible

        user = _build_user(classification="RESTRICTED")
        assert is_classification_accessible(user, "RESTRICTED") is True

        restricted_clearance_denied = _build_user(classification="UNRESTRICTED")
        assert is_classification_accessible(restricted_clearance_denied, "RESTRICTED") is False


# ---------------------------------------------------------------------------
# GET /api/v2/case/<id> — generic 404 semantics
# ---------------------------------------------------------------------------


class TestGetCaseClassification:
    """GET on a classified case must be indistinguishable from a missing one."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_classified_case_returns_generic_404(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """A case above the user's clearance returns the same 404 as a missing case."""
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get.return_value = {
            "case_id": "case-001",
            "classification": "RESTRICTED",
        }

        with request_context.test_request_context(headers={"Authorization": "Bearer ."}):
            from howler.api.v2.case import get_case

            result: Response = get_case("case-001")

            assert result.status_code == 404
            assert result.get_json()["api_error_message"] == "Case case-001 does not exist"

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_accessible_case_returns_200(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """A case at or below the user's clearance is returned normally."""
        user = _build_user(classification="RESTRICTED")
        _mock_auth(mock_auth_service, user)

        case_data = {"case_id": "case-001", "classification": "RESTRICTED"}
        mock_datastore.return_value.case.get.return_value = case_data

        with request_context.test_request_context(headers={"Authorization": "Bearer ."}):
            from howler.api.v2.case import get_case

            result: Response = get_case("case-001")

            assert result.status_code == 200
            assert result.get_json()["api_response"]["case_id"] == "case-001"

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_admin_bypasses_case_classification(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """Admin-type users can access cases above their own classification."""
        user = _build_user(user_type=["admin", "user"], classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get.return_value = {
            "case_id": "case-001",
            "classification": "RESTRICTED",
        }

        with request_context.test_request_context(headers={"Authorization": "Bearer ."}):
            from howler.api.v2.case import get_case

            result: Response = get_case("case-001")

            assert result.status_code == 200


# ---------------------------------------------------------------------------
# Mutating case endpoints — access checked before any modification
# ---------------------------------------------------------------------------


class TestCaseMutationClassification:
    """Updates, hides, and item appends must not act on inaccessible cases."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_update_classified_case_returns_404_and_skips_service(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get.return_value = {
            "case_id": "case-001",
            "classification": "RESTRICTED",
        }

        with request_context.test_request_context(
            method="PUT",
            json={"title": "New Title"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import update_case

            result: Response = update_case("case-001", user=user)

            assert result.status_code == 404
            mock_case_service.update_case.assert_not_called()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_hide_cases_treats_inaccessible_as_nonexistent(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """Inaccessible cases are reported in the same 404 as missing cases."""
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        def fake_get(case_id, **kwargs):
            if case_id == "case-002":
                return {"case_id": case_id, "classification": "RESTRICTED"}
            return {"case_id": case_id, "classification": "UNRESTRICTED"}

        mock_datastore.return_value.case.get.side_effect = fake_get

        with request_context.test_request_context(
            method="POST",
            json=["case-001", "case-002"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import hide_cases

            result: Response = hide_cases(user=user)

            assert result.status_code == 404
            # Only the restricted case is listed as "not found"
            error_message = result.get_json()["api_error_message"]
            assert "case-001" not in error_message
            assert "case-002" in error_message
            mock_case_service.hide_cases.assert_not_called()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_append_inaccessible_hit_returns_generic_404(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """Attaching a hit above the user's clearance looks like a missing hit."""
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get.return_value = {
            "case_id": "case-001",
            "classification": "UNRESTRICTED",
        }
        mock_datastore.return_value.__getitem__.return_value.get.return_value = {
            "howler": {"id": "hit-001"},
            "classification": "RESTRICTED",
        }

        with request_context.test_request_context(
            method="POST",
            json={"type": "hit", "value": "hit-001", "name": "Hit 001"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import append_item

            result: Response = append_item("case-001", user=user)

            assert result.status_code == 404
            assert result.get_json()["api_error_message"] == "hit hit-001 does not exist"
            mock_case_service.append_case_item.assert_not_called()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_append_accessible_hit_succeeds(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="RESTRICTED")
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get.return_value = {
            "case_id": "case-001",
            "classification": "UNRESTRICTED",
        }
        mock_datastore.return_value.__getitem__.return_value.get.return_value = {
            "classification": "RESTRICTED",
        }
        mock_case_service.append_case_item.return_value = Case({"case_id": "case-001", "title": "T", "summary": "S"})

        with request_context.test_request_context(
            method="POST",
            json={"type": "hit", "value": "hit-001", "name": "Hit 001"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import append_item

            result: Response = append_item("case-001", user=user)

            assert result.status_code == 200
            mock_case_service.append_case_item.assert_called_once()


# ---------------------------------------------------------------------------
# Classification escalation through payloads -> 400
# ---------------------------------------------------------------------------


class TestClassificationEscalation:
    """Creating/updating documents at classifications above clearance is invalid input."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_create_case_above_user_classification_returns_400(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="POST",
            json={"title": "T", "summary": "S", "classification": "RESTRICTED"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import create_case

            result: Response = create_case(user=user)

            assert result.status_code == 400
            mock_case_service.create_case.assert_not_called()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.login.auth_service")
    def test_update_case_escalation_returns_400(
        self, mock_auth_service, mock_case_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """A user cannot raise a case's classification above their clearance."""
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get.return_value = {
            "case_id": "case-001",
            "classification": "UNRESTRICTED",
        }

        with request_context.test_request_context(
            method="PUT",
            json={"classification": "RESTRICTED"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import update_case

            result: Response = update_case("case-001", user=user)

            assert result.status_code == 400
            mock_case_service.update_case.assert_not_called()


# ---------------------------------------------------------------------------
# v1 hit endpoints
# ---------------------------------------------------------------------------


class TestCreateHitsClassification:
    """POST /api/v1/hit/ must reject records above the user's clearance."""

    @patch("howler.api.v1.hit.hit_service")
    @patch("howler.security.login.auth_service")
    def test_create_hits_above_classification_rejected(
        self, mock_auth_service, mock_hit_service, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        restricted_hit: Hit = random_model_obj(cast(Model, Hit))
        restricted_hit.classification = "RESTRICTED"
        mock_hit_service.convert_hit.return_value = (restricted_hit, [])

        with request_context.test_request_context(
            method="POST",
            json=[{"howler": {"id": "hit-001"}}],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v1.hit import create_hits

            result: Response = create_hits(user=user)

            assert result.status_code == 400
            body = result.get_json()
            assert len(body["api_response"]["invalid"]) == 1
            assert "User cannot create hits at classification RESTRICTED" in body["api_response"]["invalid"][0]["error"]
            mock_hit_service.create_hits.assert_not_called()

    @patch("howler.api.v1.hit.correlation_service")
    @patch("howler.api.v1.hit.action_service")
    @patch("howler.api.v1.hit.analytic_service")
    @patch("howler.api.v1.hit.hit_service")
    @patch("howler.security.login.auth_service")
    def test_create_hits_at_accessible_classification_succeeds(
        self,
        mock_auth_service,
        mock_hit_service,
        mock_analytic_service,
        mock_action_service,
        mock_correlation_service,
        stub_classification,
        request_context: Flask,
    ):
        user = _build_user(classification="RESTRICTED")
        _mock_auth(mock_auth_service, user)

        accessible_hit: Hit = random_model_obj(cast(Model, Hit))
        accessible_hit.classification = "RESTRICTED"
        accessible_hit.event = None
        mock_hit_service.convert_hit.return_value = (accessible_hit, [])
        mock_hit_service.create_hits.return_value = True

        with request_context.test_request_context(
            method="POST",
            json=[{"howler": {"id": "hit-001"}}],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v1.hit import create_hits

            result: Response = create_hits(user=user)

            assert result.status_code == 201
            mock_hit_service.create_hits.assert_called_once()


class TestUpdateByQueryAccessControl:
    """PUT /api/v1/hit/update must scope bulk updates to the user's clearance."""

    def _run(self, request_context, user, payload):
        with request_context.test_request_context(
            method="PUT",
            json=payload,
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v1.hit import update_by_query

            return update_by_query(user=user)

    @patch("howler.api.v1.hit.datastore")
    @patch("howler.security.login.auth_service")
    def test_bulk_update_propagates_access_control_filter(
        self, mock_auth_service, mock_datastore, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="UNRESTRICTED")
        user.access_control = "(__access_lvl__:[0 TO 100])"
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.hit.update_by_query.return_value = 5

        result = self._run(
            request_context,
            user,
            {"query": "howler.id:*", "operations": [["SET", "howler.status", "open"]]},
        )

        assert result.status_code == 200
        assert result.get_json()["api_response"]["success"] is True
        _, kwargs = mock_datastore.return_value.hit.update_by_query.call_args
        assert kwargs["access_control"] == "(__access_lvl__:[0 TO 100])"

    @patch("howler.api.v1.hit.datastore")
    @patch("howler.security.login.auth_service")
    def test_bulk_update_without_access_control_uses_no_filter(
        self, mock_auth_service, mock_datastore, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="UNRESTRICTED")
        user.access_control = None
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.hit.update_by_query.return_value = 5

        result = self._run(
            request_context,
            user,
            {"query": "howler.id:*", "operations": [["SET", "howler.status", "open"]]},
        )

        assert result.status_code == 200
        _, kwargs = mock_datastore.return_value.hit.update_by_query.call_args
        assert kwargs["access_control"] is None

    @patch("howler.api.v1.hit.datastore")
    @patch("howler.security.login.auth_service")
    def test_bulk_update_rejects_classification_operation(
        self, mock_auth_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """Bulk updates cannot change classification: script updates bypass ODM
        serialization and would leave the __access_* bookkeeping fields stale."""
        user = _build_user(classification="RESTRICTED")
        _mock_auth(mock_auth_service, user)

        result = self._run(
            request_context,
            user,
            {"query": "howler.id:*", "operations": [["SET", "classification", "UNRESTRICTED"]]},
        )

        assert result.status_code == 400
        assert "protected field classification" in result.get_json()["api_error_message"]
        mock_datastore.return_value.hit.update_by_query.assert_not_called()

    @patch("howler.api.v1.hit.datastore")
    @patch("howler.security.login.auth_service")
    def test_bulk_update_rejects_access_bookkeeping_operations(
        self, mock_auth_service, mock_datastore, stub_classification, request_context: Flask
    ):
        """Rewriting __access_lvl__ directly would make documents visible to
        lower-clearance users in search results."""
        user = _build_user(classification="RESTRICTED")
        _mock_auth(mock_auth_service, user)

        for field in ("__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"):
            result = self._run(
                request_context,
                user,
                {"query": "howler.id:*", "operations": [["SET", field, 0]]},
            )

            assert result.status_code == 400, field
            assert f"protected field {field}" in result.get_json()["api_error_message"]

        mock_datastore.return_value.hit.update_by_query.assert_not_called()


class TestBundleEndpointClassification:
    """Deprecated bundle shims must not leak classified hits."""

    @patch("howler.api.v1.hit.hit_service")
    @patch("howler.security.login.auth_service")
    def test_update_bundle_classified_root_returns_generic_404(
        self, mock_auth_service, mock_hit_service, stub_classification, request_context: Flask
    ):
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        root: Hit = random_model_obj(cast(Model, Hit))
        root.classification = "RESTRICTED"
        mock_hit_service.get_hit.return_value = root

        # The endpoint denies access before ever reaching the service layer
        with patch("howler.services.bundle_compat_service.add_to_bundle") as mock_add:
            with request_context.test_request_context(
                method="PUT",
                json=["child-001"],
                headers={"Authorization": "Bearer ."},
            ):
                from howler.api.v1.hit import update_bundle

                result: Response = update_bundle("root-001", user=user)

                assert result.status_code == 404
                assert result.get_json()["api_error_message"] == "Bundle hit root-001 does not exist"
                mock_add.assert_not_called()

    @patch("howler.api.v1.hit.hit_service")
    @patch("howler.services.bundle_compat_service.add_to_bundle")
    @patch("howler.security.login.auth_service")
    def test_update_bundle_drops_inaccessible_children(
        self, mock_auth_service, mock_add_to_bundle, mock_hit_service, stub_classification, request_context: Flask
    ):
        """Children above the user's clearance are silently dropped, like missing ones."""
        user = _build_user(classification="UNRESTRICTED")
        _mock_auth(mock_auth_service, user)

        root: Hit = random_model_obj(cast(Model, Hit))
        root.classification = "UNRESTRICTED"
        accessible_child: Hit = random_model_obj(cast(Model, Hit))
        accessible_child.classification = "UNRESTRICTED"
        restricted_child: Hit = random_model_obj(cast(Model, Hit))
        restricted_child.classification = "RESTRICTED"

        hits_by_id = {
            "root-001": root,
            "child-001": accessible_child,
            "child-002": restricted_child,
        }
        mock_hit_service.get_hit.side_effect = lambda hit_id, **kwargs: hits_by_id[hit_id]
        mock_add_to_bundle.return_value = {"howler": {"id": "root-001"}}

        with request_context.test_request_context(
            method="PUT",
            json=["child-001", "child-002"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v1.hit import update_bundle

            result: Response = update_bundle("root-001", user=user)

            assert result.status_code == 200
            # Only the accessible child survives the filter
            mock_add_to_bundle.assert_called_once_with("root-001", ["child-001"], refresh=None)
