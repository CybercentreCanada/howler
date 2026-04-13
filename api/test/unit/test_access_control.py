"""Unit tests for classification-based access control (PR #233).

These tests verify the classification engine, access-control query building,
dynamic classification computation, and OAuth profile role/group resolution
from an "already-authenticated" perspective -- no HTTP or live server required.

Classification config under test (test/classification.yml):
    Levels:   UNRESTRICTED (U, lvl=100)  <  RESTRICTED (R, lvl=200)
    Required: ADMIN (ADM/GOD), SUPER USER (SU)
    Groups:   DEPARTMENT 1 (D1), DEPARTMENT 2 (D2)
    Subgroups: GROUP 1 (G1, requires D1), GROUP 2 (G2)
"""

import os
from copy import deepcopy
from unittest.mock import patch

import pytest

from howler.common import loader
from howler.common.classification import Classification
from howler.common.exceptions import InvalidClassification
from howler.helper import oauth as oauth_module
from howler.odm.models.config import OAuthProvider
from howler.services import user_service

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

YML_CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "classification.yml")


@pytest.fixture()
def cl_engine() -> Classification:
    """Return a fresh ClassificationEngine loaded from the test YAML."""
    return loader.get_classification(yml_config=YML_CONFIG)


@pytest.fixture()
def cl_engine_dynamic_email() -> Classification:
    """ClassificationEngine with dynamic_groups enabled (email type)."""
    eng = loader.get_classification(yml_config=YML_CONFIG)
    eng = deepcopy(eng)
    eng.dynamic_groups = True
    eng.dynamic_groups_type = "email"
    return eng


@pytest.fixture()
def cl_engine_dynamic_group() -> Classification:
    """ClassificationEngine with dynamic_groups enabled (group type)."""
    eng = loader.get_classification(yml_config=YML_CONFIG)
    eng = deepcopy(eng)
    eng.dynamic_groups = True
    eng.dynamic_groups_type = "group"
    return eng


@pytest.fixture()
def cl_engine_dynamic_all() -> Classification:
    """ClassificationEngine with dynamic_groups enabled (all type)."""
    eng = loader.get_classification(yml_config=YML_CONFIG)
    eng = deepcopy(eng)
    eng.dynamic_groups = True
    eng.dynamic_groups_type = "all"
    return eng


def _minimal_provider(**overrides) -> OAuthProvider:
    """Build a minimal OAuthProvider with sensible defaults for testing."""
    defaults = {
        "scope": "openid",
        "jwks_uri": "https://example.com/.well-known/jwks.json",
    }
    defaults.update(overrides)
    return OAuthProvider(**defaults)


# ===================================================================
# Group A -- Classification Engine: is_accessible / build / parts
# ===================================================================


class TestClassificationEngine:
    """Direct ClassificationEngine tests with the test/classification.yml config."""

    # -- is_accessible -------------------------------------------------

    def test_is_accessible_u_user_u_hit(self, cl_engine: Classification):
        """An UNRESTRICTED user can access an UNRESTRICTED hit -- same level, no barriers."""
        assert cl_engine.is_accessible(cl_engine.UNRESTRICTED, cl_engine.UNRESTRICTED)

    def test_is_accessible_u_user_r_hit(self, cl_engine: Classification):
        """An UNRESTRICTED user CANNOT access a RESTRICTED hit -- hit level exceeds user level."""
        assert not cl_engine.is_accessible(cl_engine.UNRESTRICTED, cl_engine.RESTRICTED)

    def test_is_accessible_r_user_u_hit(self, cl_engine: Classification):
        """A RESTRICTED user CAN access an UNRESTRICTED hit -- user level is higher."""
        assert cl_engine.is_accessible(cl_engine.RESTRICTED, cl_engine.UNRESTRICTED)

    def test_is_accessible_r_user_r_hit(self, cl_engine: Classification):
        """A RESTRICTED user CAN access a RESTRICTED hit -- equal level, no extra markings."""
        assert cl_engine.is_accessible(cl_engine.RESTRICTED, cl_engine.RESTRICTED)

    def test_is_accessible_group_membership_required(self, cl_engine: Classification):
        """A hit classified with a group (D1) is NOT accessible to a user without that group."""
        # User has RESTRICTED level but only department 2 (REL TO form -- no solitary name)
        user_c12n = "RESTRICTED//REL TO DEPARTMENT 2"
        # Hit requires D1 (expressed via its solitary display name ANY) plus subgroup G1
        hit_c12n = "UNRESTRICTED//ANY/GROUP 1"
        assert not cl_engine.is_accessible(user_c12n, hit_c12n)

    def test_is_accessible_group_membership_satisfied(self, cl_engine: Classification):
        """A hit classified with group D1 IS accessible to a user who has that group."""
        user_c12n = cl_engine.RESTRICTED  # RESTRICTED//ADMIN//ANY includes D1
        # D1 expressed via its solitary display name ANY (no separate DEPARTMENT 1 appended)
        hit_c12n = "UNRESTRICTED//ANY"
        assert cl_engine.is_accessible(user_c12n, hit_c12n)

    def test_is_accessible_required_marking_blocks(self, cl_engine: Classification):
        """A hit with the ADMIN required marking blocks a user who lacks it."""
        # User: RESTRICTED + D1 (ANY) but NO required markings
        user_c12n = "RESTRICTED//ANY"
        # Hit: RESTRICTED + ADMIN required + D1 (ANY)
        hit_c12n = "RESTRICTED//ADMIN//ANY"
        assert not cl_engine.is_accessible(user_c12n, hit_c12n)

    def test_is_accessible_required_marking_satisfied(self, cl_engine: Classification):
        """A user with the ADMIN required marking can access a hit that requires it."""
        user_c12n = cl_engine.RESTRICTED  # RESTRICTED//ADMIN//ANY includes ADMIN required
        # Same classification as RESTRICTED (ADMIN required + D1 via solitary ANY)
        hit_c12n = "RESTRICTED//ADMIN//ANY"
        assert cl_engine.is_accessible(user_c12n, hit_c12n)

    # -- build_user_classification ------------------------------------

    def test_build_user_classification_combines_levels(self, cl_engine: Classification):
        """Merging UNRESTRICTED and RESTRICTED yields the higher level (RESTRICTED)."""
        result = cl_engine.build_user_classification(cl_engine.UNRESTRICTED, cl_engine.RESTRICTED)
        # The result should be at least RESTRICTED level
        parts = cl_engine.get_access_control_parts(result, user_classification=True)
        assert parts["__access_lvl__"] == 200

    def test_build_user_classification_combines_groups(self, cl_engine: Classification):
        """Merging two different group-level classifications includes groups from both."""
        # D1's solitary display name is ANY; D2 requires the REL TO form
        c1 = "UNRESTRICTED//ANY"
        c2 = "UNRESTRICTED//REL TO DEPARTMENT 2"
        result = cl_engine.build_user_classification(c1, c2)
        # get_access_control_parts uses long_format=False, so groups appear as short names
        parts = cl_engine.get_access_control_parts(result, user_classification=True)
        assert "D1" in parts["__access_grp1__"]
        assert "D2" in parts["__access_grp1__"]

    # -- get_access_control_parts -------------------------------------

    def test_get_access_control_parts_unrestricted(self, cl_engine: Classification):
        """UNRESTRICTED user -> __access_lvl__ == 100 (the UNRESTRICTED level value)."""
        parts = cl_engine.get_access_control_parts(cl_engine.UNRESTRICTED, user_classification=True)
        assert parts["__access_lvl__"] == 100

    def test_get_access_control_parts_restricted(self, cl_engine: Classification):
        """RESTRICTED user -> __access_lvl__ == 200 (the RESTRICTED level value)."""
        parts = cl_engine.get_access_control_parts(cl_engine.RESTRICTED, user_classification=True)
        assert parts["__access_lvl__"] == 200

    def test_get_access_control_parts_returns_all_keys(self, cl_engine: Classification):
        """The returned dict always contains the four standard access control keys."""
        parts = cl_engine.get_access_control_parts(cl_engine.UNRESTRICTED, user_classification=True)
        assert "__access_lvl__" in parts
        assert "__access_req__" in parts
        assert "__access_grp1__" in parts
        assert "__access_grp2__" in parts


# ===================================================================
# Group B -- user_service.add_access_control
# ===================================================================


class TestAddAccessControl:
    """Test that add_access_control() builds the right Lucene filter query."""

    def test_add_access_control_unrestricted_user(self, cl_engine: Classification):
        """An UNRESTRICTED user's access_control query limits __access_lvl__ to [0 TO 100]."""
        user = {"classification": cl_engine.UNRESTRICTED}
        with patch.object(user_service, "CLASSIFICATION", cl_engine):
            user_service.add_access_control(user)
        assert "__access_lvl__:[0 TO 100]" in user["access_control"]

    def test_add_access_control_restricted_user(self, cl_engine: Classification):
        """A RESTRICTED user's access_control query limits __access_lvl__ to [0 TO 200]."""
        user = {"classification": cl_engine.RESTRICTED}
        with patch.object(user_service, "CLASSIFICATION", cl_engine):
            user_service.add_access_control(user)
        assert "__access_lvl__:[0 TO 200]" in user["access_control"]

    def test_add_access_control_sets_key(self, cl_engine: Classification):
        """After calling add_access_control, the 'access_control' key exists in the user dict."""
        user = {"classification": cl_engine.UNRESTRICTED}
        with patch.object(user_service, "CLASSIFICATION", cl_engine):
            user_service.add_access_control(user)
        assert "access_control" in user
        assert isinstance(user["access_control"], str)
        assert len(user["access_control"]) > 0


# ===================================================================
# Group C -- user_service.get_dynamic_classification
# ===================================================================


class TestGetDynamicClassification:
    """Test dynamic classification computation.

    The function normalizes the user's base classification and, when dynamic
    groups are enabled, appends email-domain and/or group-based group markings.
    """

    def test_returns_normalized_base_when_dynamic_groups_disabled(self, cl_engine: Classification):
        """With dynamic_groups=False, the classification is simply normalized (no group expansion)."""
        user_info = {"classification": cl_engine.UNRESTRICTED, "email": "alice@example.com"}
        with patch.object(user_service, "CLASSIFICATION", cl_engine):
            result = user_service.get_dynamic_classification(user_info)
        # Should be the normalized UNRESTRICTED -- no dynamic group appended
        assert result == cl_engine.UNRESTRICTED

    def test_email_type_appends_domain(self, cl_engine_dynamic_email: Classification):
        """With dynamic_groups=True and type='email', the email domain is added as a group."""
        user_info = {"classification": cl_engine_dynamic_email.UNRESTRICTED, "email": "alice@example.com"}
        with patch.object(user_service, "CLASSIFICATION", cl_engine_dynamic_email):
            result = user_service.get_dynamic_classification(user_info)
        # Should contain the uppercased domain as a group
        assert "EXAMPLE.COM" in result

    def test_group_type_appends_groups(self, cl_engine_dynamic_group: Classification):
        """With dynamic_groups=True and type='group', user groups are added as classification groups."""
        user_info = {
            "classification": cl_engine_dynamic_group.UNRESTRICTED,
            "email": "alice@example.com",
            "groups": ["teamA", "teamB"],
        }
        with patch.object(user_service, "CLASSIFICATION", cl_engine_dynamic_group):
            result = user_service.get_dynamic_classification(user_info)
        # Groups should appear (uppercased by the classification engine)
        assert "TEAMA" in result.upper()
        assert "TEAMB" in result.upper()

    def test_all_type_appends_email_and_groups(self, cl_engine_dynamic_all: Classification):
        """With dynamic_groups_type='all', both email domain and groups are appended."""
        user_info = {
            "classification": cl_engine_dynamic_all.UNRESTRICTED,
            "email": "bob@corp.io",
            "groups": ["ops"],
        }
        with patch.object(user_service, "CLASSIFICATION", cl_engine_dynamic_all):
            result = user_service.get_dynamic_classification(user_info)
        assert "CORP.IO" in result
        assert "OPS" in result.upper()

    def test_no_email_skips_email_path(self, cl_engine_dynamic_email: Classification):
        """When email is absent and type='email', no dynamic group is appended."""
        user_info = {"classification": cl_engine_dynamic_email.UNRESTRICTED}
        with patch.object(user_service, "CLASSIFICATION", cl_engine_dynamic_email):
            result = user_service.get_dynamic_classification(user_info)
        # Should just be the base classification, since we have no email
        assert result == cl_engine_dynamic_email.UNRESTRICTED

    def test_empty_groups_skips_group_path(self, cl_engine_dynamic_group: Classification):
        """When groups list is empty and type='group', no dynamic group is appended."""
        user_info = {
            "classification": cl_engine_dynamic_group.UNRESTRICTED,
            "email": "alice@example.com",
            "groups": [],
        }
        with patch.object(user_service, "CLASSIFICATION", cl_engine_dynamic_group):
            result = user_service.get_dynamic_classification(user_info)
        assert result == cl_engine_dynamic_group.UNRESTRICTED


# ===================================================================
# Group D -- oauth.parse_profile: role_map and new auto_property types
# ===================================================================


class TestParseProfileRoleMap:
    """Test the role_map feature that maps OAuth group IDs to Howler roles."""

    def test_role_map_assigns_role(self):
        """When the user's OAuth groups contain a group mapped to 'admin', that role is added."""
        profile = {
            "email": "alice@example.com",
            "groups": ["security-admins"],
        }
        provider = _minimal_provider(role_map={"admin": "security-admins"})
        result = oauth_module.parse_profile(profile, provider)
        # 'admin' should be in the resulting type list alongside the default 'user'
        assert "admin" in result["type"]
        assert "user" in result["type"]

    def test_role_map_no_match_keeps_default(self):
        """When OAuth groups don't match any role_map entry, only the default 'user' role is kept."""
        profile = {
            "email": "bob@example.com",
            "groups": ["some-other-group"],
        }
        provider = _minimal_provider(role_map={"admin": "security-admins"})
        result = oauth_module.parse_profile(profile, provider)
        assert result["type"] == ["user"]

    def test_role_map_ignored_when_no_profile_groups(self):
        """When the profile has no 'groups' key at all, role_map has no effect."""
        profile = {"email": "carol@example.com"}
        provider = _minimal_provider(role_map={"admin": "security-admins"})
        result = oauth_module.parse_profile(profile, provider)
        assert result["type"] == ["user"]

    def test_role_map_multiple_roles(self):
        """Multiple matching groups can assign multiple distinct roles."""
        profile = {
            "email": "dave@example.com",
            "groups": ["admins-group", "auto-basic-group"],
        }
        provider = _minimal_provider(
            role_map={
                "admin": "admins-group",
                "automation_basic": "auto-basic-group",
            }
        )
        result = oauth_module.parse_profile(profile, provider)
        assert "admin" in result["type"]
        assert "automation_basic" in result["type"]
        assert "user" in result["type"]

    def test_role_map_does_not_duplicate_existing_role(self):
        """If 'user' is already in roles (default), role_map won't add it again."""
        profile = {
            "email": "eve@example.com",
            "groups": ["users-group"],
        }
        provider = _minimal_provider(role_map={"user": "users-group"})
        result = oauth_module.parse_profile(profile, provider)
        assert result["type"].count("user") == 1


class TestParseProfileAutoProperties:
    """Test the new auto_property types: 'group' and 'assignment', plus existing types."""

    def test_group_auto_property_appends_group(self):
        """An auto_property of type='group' adds the group when the pattern matches."""
        profile = {"email": "alice@acme.com", "preferred_username": "alice@acme.com"}
        provider = _minimal_provider(
            auto_properties=[
                {
                    "field": "email",
                    "pattern": ".*@acme\\.com$",
                    "type": "group",
                    "value": "acme-team",
                }
            ]
        )
        result = oauth_module.parse_profile(profile, provider)
        assert "acme-team" in result["groups"]

    def test_group_auto_property_unmatched(self):
        """When the pattern doesn't match, the group is NOT added."""
        profile = {"email": "bob@other.com"}
        provider = _minimal_provider(
            auto_properties=[
                {
                    "field": "email",
                    "pattern": ".*@acme\\.com$",
                    "type": "group",
                    "value": "acme-team",
                }
            ]
        )
        result = oauth_module.parse_profile(profile, provider)
        assert "acme-team" not in result["groups"]

    def test_classification_auto_property(self):
        """A type='classification' auto_property upgrades the user classification on match."""
        profile = {"email": "admin@secret.gov", "department": "classified-ops"}
        provider = _minimal_provider(
            auto_properties=[
                {
                    "field": "department",
                    "pattern": "classified.*",
                    "type": "classification",
                    "value": "RESTRICTED",
                }
            ]
        )
        result = oauth_module.parse_profile(profile, provider)
        # Classification should be at least RESTRICTED
        assert "RESTRICTED" in result["classification"].upper()

    def test_access_auto_property_deny(self):
        """A type='access' auto_property with value='False' denies access when the pattern matches."""
        profile = {"email": "blocked@example.com", "status": "disabled"}
        provider = _minimal_provider(
            auto_properties=[
                {
                    "field": "status",
                    "pattern": "disabled",
                    "type": "access",
                    "value": "False",
                }
            ]
        )
        result = oauth_module.parse_profile(profile, provider)
        # The default access is toggled to False when the pattern matches with value="False"
        # (auto_property type="access" flips the default when pattern="False" and it matches)
        assert result["access"] is False

    def test_role_auto_property(self):
        """A type='role' auto_property adds a role when the pattern matches."""
        profile = {"email": "op@example.com", "job": "operator"}
        provider = _minimal_provider(
            auto_properties=[
                {
                    "field": "job",
                    "pattern": "operator",
                    "type": "role",
                    "value": "automation_basic",
                }
            ]
        )
        result = oauth_module.parse_profile(profile, provider)
        assert "automation_basic" in result["type"]

    def test_defaults_no_config(self):
        """With no auto_properties and no role_map, defaults are: type=['user'], UNRESTRICTED, access=True."""
        profile = {"email": "new@example.com"}
        provider = _minimal_provider()
        result = oauth_module.parse_profile(profile, provider)
        assert result["type"] == ["user"]
        assert result["access"] is True
        # Classification should be the engine's UNRESTRICTED value
        assert "UNRESTRICTED" in result["classification"].upper() or "U" == result["classification"]


# ===================================================================
# Group E -- has_access_control (search.py)
# ===================================================================


class TestHasAccessControl:
    """Verify that the hit index is access-controlled and others are not."""

    def test_hit_index_is_access_controlled(self):
        """The 'hit' index is in ACCESS_CONTROLLED_INDICES -- search queries will be filtered."""
        from howler.helper.search import has_access_control

        assert has_access_control("hit") is True

    def test_user_index_is_not_access_controlled(self):
        """The 'user' index is NOT access-controlled -- no classification filter applied."""
        from howler.helper.search import has_access_control

        assert has_access_control("user") is False

    def test_analytic_index_is_not_access_controlled(self):
        """The 'analytic' index is NOT access-controlled."""
        from howler.helper.search import has_access_control

        assert has_access_control("analytic") is False


class TestExampleClassifications:
    @pytest.mark.parametrize(
        "c12n",
        [
            "RESTRICTED//ADMIN//GROUP 2",  # level + required + subgroup (no group needed for G2)
            "UNRESTRICTED//ANY",  # D1 via solitary display name
            "UNRESTRICTED//REL TO DEPARTMENT 2",  # D2 via explicit REL TO form
            "UNRESTRICTED//ANY/GROUP 1",  # D1 (ANY) + G1 (requires D1, satisfied)
            "UNRESTRICTED//REL TO DEPARTMENT 2/GROUP 2",  # D2 + G2 (no group constraint on G2)
        ],
    )
    def test_valid_classifications(self, cl_engine: Classification, c12n: str):
        cl_engine.get_access_control_parts(c12n)

    @pytest.mark.parametrize(
        "c12n",
        [
            "RESTRICTED//ADMIN//REL TO GROUP 2",  # REL TO is for groups; GROUP 2 is a subgroup
            "UNRESTRICTED//REL TO DEPARTMENT 2/GROUP 1",  # G1 is limited_to_group D1, but only D2 present
        ],
    )
    def test_invalid_classifications(self, cl_engine: Classification, c12n: str):
        with pytest.raises(InvalidClassification):
            cl_engine.get_access_control_parts(c12n)
