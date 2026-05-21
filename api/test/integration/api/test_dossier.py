import json
from collections.abc import Callable
from typing import Any

import pytest
import requests

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.dossier import Dossier
from howler.odm.random_data import create_dossiers, wipe_dossiers
from test.conftest import APIError, get_api_data


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_dossiers(ds)

        yield ds
    finally:
        wipe_dossiers(ds)


# noinspection PyUnusedLocal
def test_add_dossier(datastore: HowlerDatastore, login_session):
    session, host = login_session

    dossier_data: dict[str, Any] = {"leads": []}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/dossier/",
            method="POST",
            data=json.dumps(dossier_data),
        )

    assert "title" in str(err.value)

    dossier_data["title"] = "Test dossier"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/dossier/",
            method="POST",
            data=json.dumps(dossier_data),
        )

    assert "query" in str(err.value)

    dossier_data["query"] = "howler.id:*"
    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/dossier/",
            method="POST",
            data=json.dumps(dossier_data),
        )

    assert "type" in str(err.value)

    dossier_data["type"] = "personal"

    resp = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps(dossier_data),
    )

    assert resp["owner"] == ["admin"]

    dossier_data["type"] = "global"
    resp = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps(dossier_data),
    )

    assert resp["owner"] == ["admin"]


# noinspection PyUnusedLocal
def test_get_dossiers(datastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/dossier/")

    assert all(t["type"] == "global" or t["owner"] in [["admin"], ["none"]] for t in resp)


# noinspection PyUnusedLocal
def test_remove_dossier(datastore: HowlerDatastore, login_session):
    session, host = login_session

    datastore.dossier.commit()
    total = datastore.dossier.search("dossier_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*", "leads": []}),
    )

    datastore.dossier.commit()
    assert total + 1 == datastore.dossier.search("dossier_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/dossier/{create_res['dossier_id']}/", method="DELETE")

    datastore.dossier.commit()
    assert res is None
    assert total == datastore.dossier.search("dossier_id:*")["total"]


# noinspection PyUnusedLocal
def test_set_dossier(datastore: HowlerDatastore, login_session):
    session, host = login_session

    dossier_id = datastore.dossier.search("owner:admin")["items"][0]["dossier_id"]

    resp = get_api_data(
        session,
        f"{host}/api/v1/dossier/{dossier_id}/",
        method="PUT",
        data=json.dumps({"title": "new title thing"}),
    )
    assert resp["title"] == "new title thing"

    datastore.dossier.commit()

    updated_dossier = datastore.dossier.get(dossier_id, as_obj=True)
    assert updated_dossier.title == "new title thing"


# noinspection PyUnusedLocal
def test_get_dossier_for_hit(datastore: HowlerDatastore, login_session):
    session, host = login_session

    # Create a test hit with a unique howler.id
    test_hit_id = "test-hit-for-dossier-matching"
    hit_data = {
        "howler": {
            "id": test_hit_id,
            "analytic": "Test analytic for dossier matching",
            "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48cc",
            "score": "0.8",
            "assignment": "admin",
            "outline": {
                "threat": "10.0.0.1",
                "target": "test-target",
                "indicators": ["test-indicator"],
                "summary": "Test hit for dossier matching",
            },
        },
        "event": {
            "provider": "test",
        },
    }

    # Save the hit to the datastore
    datastore.hit.save(test_hit_id, hit_data)
    datastore.hit.commit()

    # Create a dossier that matches this hit (query matches the hit's howler.id)
    dossier_data = {
        "title": "Test Dossier for Hit Matching",
        "query": f'howler.id:"{test_hit_id}"',
        "type": "global",
        "leads": [],
    }

    create_res = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps(dossier_data),
    )

    created_dossier_id = create_res["dossier_id"]
    datastore.dossier.commit()

    try:
        # Test the get_dossier_for_hit endpoint
        resp = get_api_data(
            session,
            f"{host}/api/v1/dossier/hit/{test_hit_id}/",
            method="GET",
        )

        # Verify the response is a list
        assert isinstance(resp, list)

        # Check that our created dossier is in the result list
        matching_dossier_ids = [d["dossier_id"] for d in resp]
        assert created_dossier_id in matching_dossier_ids

        # Find our specific dossier in the response and verify its data
        our_dossier = next((d for d in resp if d["dossier_id"] == created_dossier_id), None)
        assert our_dossier is not None
        assert our_dossier["title"] == "Test Dossier for Hit Matching"
        assert our_dossier["query"] == f'howler.id:"{test_hit_id}"'
        assert our_dossier["type"] == "global"

    finally:
        # Clean up - delete the hit and dossier from the database
        datastore.hit.delete(test_hit_id)
        datastore.hit.commit()

        datastore.dossier.delete(created_dossier_id)
        datastore.dossier.commit()


# noinspection PyUnusedLocal
def test_get_dossier_for_hit_user_scoping(datastore: HowlerDatastore, login_session):
    "Test that get_dossier_for_hit returns global and personal-own dossiers, but not other users' personal dossiers."
    session, host = login_session

    test_hit_id = "test-hit-dossier-scoping"
    hit_data = {
        "howler": {
            "id": test_hit_id,
            "analytic": "Scoping Test Analytic",
            "hash": "ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12",
            "score": "0.5",
            "assignment": "admin",
            "outline": {
                "threat": "10.0.0.2",
                "target": "scoping-target",
                "indicators": ["scoping-indicator"],
                "summary": "Hit for user-scoping dossier test",
            },
        },
        "event": {"provider": "test"},
    }
    datastore.hit.save(test_hit_id, hit_data)
    datastore.hit.commit()

    matching_query = f'howler.id:"{test_hit_id}"'

    # Create a personal dossier owned by admin (the logged-in user) - should be returned
    personal_admin_res = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "Admin Personal Dossier", "query": matching_query, "type": "personal", "leads": []}),
    )
    personal_admin_dossier_id = personal_admin_res["dossier_id"]

    # Directly save a personal dossier owned by another user - should NOT be returned for admin
    from howler.odm.models.dossier import Dossier as DossierModel

    other_user_dossier = DossierModel(
        {
            "title": "Other User Personal Dossier",
            "query": matching_query,
            "type": "personal",
            "owner": ["other_user"],
            "leads": [],
            "administrator": [],
            "member": [],
        }
    )
    other_user_dossier_id = other_user_dossier.dossier_id
    datastore.dossier.save(other_user_dossier_id, other_user_dossier)
    datastore.dossier.commit()

    try:
        resp = get_api_data(
            session,
            f"{host}/api/v1/dossier/hit/{test_hit_id}/",
            method="GET",
        )

        assert isinstance(resp, list)

        returned_ids = [d["dossier_id"] for d in resp]

        # Admin's own personal dossier should be visible
        assert personal_admin_dossier_id in returned_ids

        # Another user's personal dossier should NOT be visible
        assert other_user_dossier_id not in returned_ids

        # All returned dossiers must be either global or owned by admin
        for dossier in resp:
            assert dossier["type"] == "global" or dossier["owner"] == ["admin"], (
                f"Unexpected dossier in results: {dossier}"
            )

    finally:
        datastore.hit.delete(test_hit_id)
        datastore.hit.commit()

        datastore.dossier.delete(personal_admin_dossier_id)
        datastore.dossier.delete(other_user_dossier_id)
        datastore.dossier.commit()


# region : Testing Permissions

# region : Permission helper


def add_permission_every_role(member_to_add: str, member_requesting, create_res, host, dossier):
    try:
        for membership in dossier.get_privilege_mapping().keys():
            get_api_data(
                member_requesting,
                f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
                method="PUT",
                data=json.dumps(
                    {
                        "user_id": member_to_add,
                        "privilege": membership,
                    }
                ),
            )
    # Error is intended sometime.
    except APIError:
        return


def remove_permission_every_role(member_to_remove: str, member_requesting, create_res, host, dossier):
    try:
        for membership in dossier.get_privilege_mapping().keys():
            get_api_data(
                member_requesting,
                f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
                method="DELETE",
                data=json.dumps(
                    {
                        "user_id": member_to_remove,
                        "privilege": membership,
                    }
                ),
            )
    # Error is intended sometime.
    except APIError:
        return


def modifying_dossier(member_requesting, create_res, host, dossier_name: str = "renamed_dossier"):
    payload = {
        "title": f"{dossier_name}",  # The name of this dossier
        "query": "howler.id:*",  # The query to run
    }
    get_api_data(
        member_requesting,
        f"{host}/api/v1/dossier/{create_res['dossier_id']}",
        method="PUT",
        data=json.dumps(payload),
    )


# endregion


def test_give_remove_membership(
    datastore: HowlerDatastore,
    user_session,
):
    """
    Test adding a user and removing a user from a dossier
    """
    owner_session, host = user_session["user"]
    member_session, _ = user_session["huey"]

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the dossier
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )
    dossier: Dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)

    # Give|Remove every possible membership
    for request in ("PUT", "DELETE"):
        for membership in dossier.get_privilege_mapping().keys():
            get_api_data(
                owner_session,
                f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
                method=request,
                data=json.dumps(
                    {
                        "user_id": member_uname,
                        "privilege": membership,
                    }
                ),
            )
            # updating the dossier for testing
            dossier: Dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
            if request == "PUT":
                assert member_uname in dossier.get_privilege_mapping()[membership]
                continue
            assert member_uname not in dossier.get_privilege_mapping()[membership]

    # Delete the dossier
    get_api_data(owner_session, f"{host}/api/v1/dossier/{create_res['dossier_id']}/", method="DELETE")


def test_owner_privilege(datastore: HowlerDatastore, user_session: dict):
    owner_session, host = user_session["user"]
    member_session, _ = user_session["huey"]

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the dossier
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "test_membership", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.dossier.commit()
    dossier: Dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    # adding|remove user to admin, member and owner
    add_permission_every_role(
        member_to_add=member_uname, create_res=create_res, member_requesting=owner_session, host=host, dossier=dossier
    )

    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    for membership in dossier.get_privilege_mapping().keys():
        assert member_uname in dossier.get_privilege_mapping()[membership]

    remove_permission_every_role(
        member_to_remove=member_uname,
        create_res=create_res,
        member_requesting=owner_session,
        host=host,
        dossier=dossier,
    )

    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    for membership in dossier.get_privilege_mapping().keys():
        assert member_uname not in dossier.get_privilege_mapping()[membership]

    # Owner should be able to modify the dossier
    modifying_dossier(member_requesting=owner_session, create_res=create_res, host=host)
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert dossier.title == "renamed_dossier"

    # Owner should be able to delete the dossier
    # Create an other temporary dossier
    total = datastore.dossier.search("dossier_id:*")["total"]

    create_res_copy = get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.dossier.commit()
    # Verify created properly
    assert total + 1 == datastore.dossier.search("dossier_id:*")["total"]

    # Giving ownership to an other user
    get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/{create_res_copy['dossier_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "privilege": "owner",
            }
        ),
    )
    datastore.dossier.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/{create_res_copy['dossier_id']}",
        method="DELETE",
    )
    datastore.dossier.commit()
    assert total == datastore.dossier.search("dossier_id:*")["total"]

    # Owner should be able to remove self if other owner exist
    get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "privilege": "owner",
            }
        ),
    )
    datastore.dossier.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": owner_uname,
                "privilege": "owner",
            }
        ),
    )
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert owner_uname not in dossier.get_privilege_mapping()["owner"]

    # Owner should not be able to remove self if no other owner exist
    try:
        get_api_data(
            member_session,
            f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
            method="DELETE",
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "privilege": "owner",
                }
            ),
        )
    except Exception:
        # The error is intentional
        pass

    datastore.dossier.commit()

    assert member_uname in dossier.get_privilege_mapping()["owner"]

    return


def test_admin(datastore: HowlerDatastore, user_session: Callable[[str], tuple[requests.Session, str]], login_session):
    """
    Test Admin privilege on view dossier and actions. This will attempt on adding, removing member from positions and
    verify that the permission an admin have are the intended ones.
    """
    admin_session, host = user_session("user")
    member_session, _ = user_session("huey")
    owner_session, _ = login_session

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    admin_uname = get_api_data(admin_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the dossier
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "test_membership", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.dossier.commit()
    dossier: Dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    # giving admin to admin
    get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": admin_uname,
                "privilege": "administrator",
            }
        ),
    )
    assert owner_uname not in dossier.get_privilege_mapping()["administrator"]  # ensure user is admin

    # Admin should be able to add|remove member and other admin
    for method in ["PUT", "DELETE"]:
        get_api_data(
            admin_session,
            f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
            method=method,
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "privilege": "administrator",
                }
            ),
        )
        datastore.dossier.commit()
        dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
        if method == "PUT":
            assert member_uname in dossier.get_privilege_mapping()["administrator"]
            continue
        assert member_uname not in dossier.get_privilege_mapping()["administrator"]

    # Admin should not be able to add|remove owner
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
            method="PUT",
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "privilege": "owner",
                }
            ),
        )
    except Exception:
        # intended to fail
        pass
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert member_uname not in dossier.get_privilege_mapping()["owner"]
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
            method="DELETE",
            data=json.dumps(
                {
                    "user_id": admin_uname,
                    "privilege": "owner",
                }
            ),
        )
    except Exception:
        # intended failed
        pass
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert admin_uname not in dossier.get_privilege_mapping()["owner"]

    # Admin should not be able to delete dossier
    total = datastore.dossier.search("dossier_id:*")["total"]
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/dossier/{create_res['dossier_id']}",
            method="DELETE",
        )
    except Exception:
        # intended fail
        pass
    datastore.dossier.commit()
    assert total == datastore.dossier.search("dossier_id:*")["total"]  # Should not have deleted

    # Admin should be able to modify the dossier
    modifying_dossier(
        member_requesting=admin_session, create_res=create_res, host=host, dossier_name="ADMIN_CHANGED_NAME"
    )
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert dossier.title == "ADMIN_CHANGED_NAME"

    # Admin should be able to remove self even if only admin
    get_api_data(
        admin_session,
        f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": admin_uname,
                "privilege": "administrator",
            }
        ),
    )
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert admin_uname not in dossier.get_privilege_mapping()["administrator"]
    assert dossier.get_privilege_mapping()["administrator"] == []

    return


def test_member(datastore: HowlerDatastore, user_session: dict):
    owner_session, host = user_session["user"]
    member_session, _ = user_session["huey"]
    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the dossier
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "test_membership", "type": "global", "query": "howler.hash:*"}),
    )
    # Giving membership to member
    datastore.dossier.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/dossier/{create_res['dossier_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "privilege": "member",
            }
        ),
    )
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert member_uname in dossier.get_privilege_mapping()["member"]  # ensure the membership was given

    # Member should not be able to add admin/owner/member
    add_permission_every_role(
        create_res=create_res, host=host, member_requesting=member_session, member_to_add=member_uname, dossier=dossier
    )
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    for membership in ["owner", "administrator"]:
        assert member_uname not in dossier.get_privilege_mapping()[membership]

    # Member should not be able to remove admin/owner/member
    # adding owner into every role
    add_permission_every_role(
        create_res=create_res, host=host, member_requesting=owner_session, member_to_add=owner_uname, dossier=dossier
    )
    # verify owner is in every role
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    for membership in dossier.get_privilege_mapping().keys():
        assert owner_uname in dossier.get_privilege_mapping()[membership]

    remove_permission_every_role(
        create_res=create_res,
        host=host,
        member_requesting=member_session,
        member_to_remove=member_uname,
        dossier=dossier,
    )
    # ensure owner is still in every role
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    for membership in dossier.get_privilege_mapping().keys():
        assert owner_uname in dossier.get_privilege_mapping()[membership]
    # Member should not be able to delete dossier
    total = datastore.dossier.search("dossier_id:*")["total"]
    try:
        get_api_data(
            member_session,
            f"{host}/api/v1/dossier/{create_res['dossier_id']}",
            method="DELETE",
        )
    except Exception:
        # intended fail
        pass

    assert total == datastore.dossier.search("dossier_id:*")["total"]  # Should not have deleted

    # Member should be able to update dossier
    modifying_dossier(
        member_requesting=member_session, create_res=create_res, host=host, dossier_name="MEMBER_CHANGED_NAME"
    )
    datastore.dossier.commit()
    dossier = datastore.dossier.get(create_res["dossier_id"], as_obj=True)
    assert dossier.title == "MEMBER_CHANGED_NAME"
    return


# endregion
