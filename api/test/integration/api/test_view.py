import json
from typing import Any

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.view import View
from howler.odm.random_data import create_views, wipe_views
from test.conftest import APIError, get_api_data


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_views(ds)

        yield ds
    finally:
        wipe_views(ds)


# noinspection PyUnusedLocal
def test_add_view(datastore: HowlerDatastore, login_session):
    session, host = login_session

    view_data: dict[str, Any] = {}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/view/",
            method="POST",
            data=json.dumps(view_data),
        )

    assert "title" in str(err.value)

    view_data["title"] = "Test View"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/view/",
            method="POST",
            data=json.dumps(view_data),
        )

    assert "query" in str(err.value)

    view_data["query"] = "howler.id:*"
    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/view/",
            method="POST",
            data=json.dumps(view_data),
        )

    assert "type" in str(err.value)

    view_data["type"] = "personal"

    resp = get_api_data(
        session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps(view_data),
    )

    assert resp["owner"] == "admin"

    view_data["type"] = "global"
    resp = get_api_data(
        session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps(view_data),
    )

    assert resp["owner"] == "admin"


# noinspection PyUnusedLocal
def test_get_views(datastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/view/")

    assert all(t["type"] == "global" or t["owner"] in ["admin", "none"] for t in resp)


# noinspection PyUnusedLocal
def test_remove_view(datastore: HowlerDatastore, login_session):
    session, host = login_session

    datastore.view.commit()
    total = datastore.view.search("view_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )

    datastore.view.commit()
    assert total + 1 == datastore.view.search("view_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/view/{create_res['view_id']}/", method="DELETE")

    datastore.view.commit()
    assert res is None
    assert total == datastore.view.search("view_id:*")["total"]


# noinspection PyUnusedLocal
def test_set_view(datastore: HowlerDatastore, login_session):
    session, host = login_session

    id = datastore.view.search("owner:admin AND type:(-readonly)")["items"][0]["view_id"]

    resp = get_api_data(
        session,
        f"{host}/api/v1/view/{id}/",
        method="PUT",
        data=json.dumps({"title": "new title thing"}),
    )
    assert resp["title"] == "new title thing"

    datastore.view.commit()

    updated_view = datastore.view.get(id, as_obj=True)
    assert updated_view.title == "new title thing"


def test_set_view_error(datastore: HowlerDatastore, login_session):
    session, host = login_session

    id = datastore.view.search("owner:admin AND type:(-readonly)")["items"][0]["view_id"]

    with pytest.raises(APIError):
        get_api_data(
            session,
            f"{host}/api/v1/view/{id}/",
            method="PUT",
            data=json.dumps({"owner": "someoneelse"}),
        )

    updated_view = datastore.view.get(id, as_obj=True)
    assert updated_view.owner != "someoneelse"


def test_favourite(datastore: HowlerDatastore, login_session):
    session, host = login_session

    uname = get_api_data(session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    view: View = datastore.view.search(f"type:global OR owner:{uname}")["items"][0]

    get_api_data(
        session,
        f"{host}/api/v1/view/{view.view_id}/favourite",
        method="POST",
        data={},
    )

    datastore.user.commit()

    assert view.view_id in datastore.user.search(f"uname:{uname}")["items"][0]["favourite_views"]

    get_api_data(
        session,
        f"{host}/api/v1/view/{view.view_id}/favourite",
        method="DELETE",
    )

    datastore.user.commit()

    assert view.view_id not in datastore.user.search(f"uname:{uname}")["items"][0]["favourite_views"]


# region : Testing Permissions

# region : Permission helper


def add_permission_every_role(member_to_add: str, member_requesting, create_res, host, view, datastore):
    try:
        for membership in ("admins", "members"):
            get_api_data(
                member_requesting,
                f"{host}/api/v1/view/{create_res['view_id']}/permission",
                method="PUT",
                data=json.dumps(
                    {
                        "user_id": member_to_add,
                        "privilege": membership,
                    }
                ),
            )
            datastore.view.commit()

            # Verify the database state using a fresh object fetch
            updated_view = datastore.view.get(create_res["view_id"], as_obj=True)
            assert member_to_add in getattr(updated_view, membership)
    except APIError:
        # Expected to fail and abort when called by unauthorized users
        return


def remove_permission_every_role(member_to_remove: str, member_requesting, create_res, host, view, datastore):
    try:
        for membership in ("admins", "members"):
            get_api_data(
                member_requesting,
                f"{host}/api/v1/view/{create_res['view_id']}/permission",
                method="DELETE",
                data=json.dumps(
                    {
                        "user_id": member_to_remove,
                        "privilege": membership,
                    }
                ),
            )
            datastore.view.commit()

            # Verify the database state using a fresh object fetch
            updated_view = datastore.view.get(create_res["view_id"], as_obj=True)
            assert member_to_remove not in getattr(updated_view, membership)
    except APIError:
        # Expected to fail and abort when called by unauthorized users
        return


def modifying_view(member_requesting, create_res, host, view_name: str = "renamed_view"):
    payload = {
        "title": f"{view_name}",  # The name of this view
        "query": "howler.id:*",  # The query to run
    }
    get_api_data(
        member_requesting,
        f"{host}/api/v1/view/{create_res['view_id']}",
        method="PUT",
        data=json.dumps(payload),
    )


# endregion


def test_give_remove_membership(
    datastore: HowlerDatastore,
    user_session,
):
    """
    Test adding a user and removing a user from a view
    """
    owner_session, host = user_session()
    member_session, _ = user_session("huey")

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    # Create the view
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.view.commit()

    # Test standard privileges (administrator, member) where auth state doesn't change
    for request in ("PUT", "DELETE"):
        view: View = datastore.view.get(create_res["view_id"], as_obj=True)
        for membership in ("admins", "members"):
            get_api_data(
                owner_session,
                f"{host}/api/v1/view/{create_res['view_id']}/permission",
                method=request,
                data=json.dumps(
                    {
                        "user_id": member_uname,
                        "privilege": membership,
                    }
                ),
            )
            datastore.view.commit()

            # Update the view object to verify DB state
            view = datastore.view.get(create_res["view_id"], as_obj=True)
            if request == "PUT":
                assert member_uname in getattr(view, membership)
            else:
                assert member_uname not in getattr(view, membership)

    # Test Ownership Transfer
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res['view_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "privilege": "owner",
            }
        ),
    )
    datastore.view.commit()

    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner == member_uname

    # Test that the new owner cannot delete themselves from ownership
    with pytest.raises(APIError):
        get_api_data(
            member_session,
            f"{host}/api/v1/view/{create_res['view_id']}/permission",
            method="DELETE",
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "privilege": "owner",
                }
            ),
        )

    # Owner can delete the view
    get_api_data(member_session, f"{host}/api/v1/view/{create_res['view_id']}/", method="DELETE")
    datastore.view.commit()


def test_owner_privilege(datastore: HowlerDatastore, user_session: dict):
    owner_session, host = user_session()
    member_session, _ = user_session("huey")

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    # Create the view
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "test_membership", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.view.commit()
    view: View = datastore.view.get(create_res["view_id"], as_obj=True)

    # Add member to every role except owner
    add_permission_every_role(
        member_to_add=member_uname,
        create_res=create_res,
        member_requesting=owner_session,
        host=host,
        view=view,
        datastore=datastore,
    )

    # Validate all roles have the member assigned, while original owner remains unchanged
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner == owner_uname
    assert member_uname in view.admins
    assert member_uname in view.members

    # Remove member from every role except owner
    remove_permission_every_role(
        member_to_remove=member_uname,
        create_res=create_res,
        member_requesting=owner_session,
        host=host,
        view=view,
        datastore=datastore,
    )

    # Validate member was cleared out of every role
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner == owner_uname
    assert member_uname not in view.admins
    assert member_uname not in view.members

    # Owner should be able to modify the view
    modifying_view(member_requesting=owner_session, create_res=create_res, host=host)
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.title == "renamed_view"

    # --- Test Ownership Transfer & Deletion Rules ---
    total = datastore.view.search("view_id:*")["total"]

    create_res_copy = get_api_data(
        owner_session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.view.commit()
    assert total + 1 == datastore.view.search("view_id:*")["total"]

    # Giving ownership to another user (huey)
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res_copy['view_id']}/permission",
        method="PUT",
        data=json.dumps({"user_id": member_uname, "privilege": "owner"}),
    )
    datastore.view.commit()

    view_copy = datastore.view.get(create_res_copy["view_id"], as_obj=True)
    assert view_copy.owner == member_uname

    # Old owner should no longer be able to delete it
    with pytest.raises(APIError):
        get_api_data(
            owner_session,
            f"{host}/api/v1/view/{create_res_copy['view_id']}",
            method="DELETE",
        )

    # Clean up the copy using the NEW owner's session (huey)
    get_api_data(
        member_session,
        f"{host}/api/v1/view/{create_res_copy['view_id']}",
        method="DELETE",
    )
    datastore.view.commit()
    assert total == datastore.view.search("view_id:*")["total"]

    # Transfer ownership on the primary view
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res['view_id']}/permission",
        method="PUT",
        data=json.dumps({"user_id": member_uname, "privilege": "owner"}),
    )
    datastore.view.commit()

    # Ensure the current active owner (huey) cannot remove themselves from ownership
    with pytest.raises(APIError):
        get_api_data(
            member_session,
            f"{host}/api/v1/view/{create_res['view_id']}/permission",
            method="DELETE",
            data=json.dumps({"user_id": member_uname, "privilege": "owner"}),
        )

    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner == member_uname

    return


def test_admin(datastore: HowlerDatastore, user_session: dict, login_session):
    admin_session, host = user_session()
    member_session, _ = user_session("huey")
    owner_session, _ = login_session

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    admin_uname = get_api_data(admin_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the view
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "test_membership", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.view.commit()
    view: View = datastore.view.get(create_res["view_id"], as_obj=True)
    # giving admin to admin
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res['view_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": admin_uname,
                "privilege": "admins",
            }
        ),
    )
    assert owner_uname not in view.admins  # ensure user is admin

    # Admin should be able to add|remove member and other admin
    for method in ["PUT", "DELETE"]:
        get_api_data(
            admin_session,
            f"{host}/api/v1/view/{create_res['view_id']}/permission",
            method=method,
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "privilege": "admins",
                }
            ),
        )
        datastore.view.commit()
        view = datastore.view.get(create_res["view_id"], as_obj=True)
        if method == "PUT":
            assert member_uname in view.admins
            continue
        assert member_uname not in view.admins

    # Admin should not be able to add|remove owner
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/view/{create_res['view_id']}/permission",
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
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner != member_uname
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/view/{create_res['view_id']}/permission",
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
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner != admin_uname

    # Admin should not be able to delete view
    total = datastore.view.search("view_id:*")["total"]
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/view/{create_res['view_id']}",
            method="DELETE",
        )
    except Exception:
        # intended fail
        pass
    datastore.view.commit()
    assert total == datastore.view.search("view_id:*")["total"]  # Should not have deleted

    # Admin should be able to modify the view
    modifying_view(member_requesting=admin_session, create_res=create_res, host=host, view_name="ADMIN_CHANGED_NAME")
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.title == "ADMIN_CHANGED_NAME"

    # Admin should be able to remove self even if only admin
    get_api_data(
        admin_session,
        f"{host}/api/v1/view/{create_res['view_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": admin_uname,
                "privilege": "admins",
            }
        ),
    )
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert admin_uname not in view.admins
    assert view.admins == []

    return


def test_member(datastore: HowlerDatastore, user_session: dict):
    owner_session, host = user_session()
    member_session, _ = user_session("huey")

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    # Create the view
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "test_membership", "type": "global", "query": "howler.hash:*"}),
    )

    # Giving membership to member
    datastore.view.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res['view_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "privilege": "members",
            }
        ),
    )
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert member_uname in view.members  # ensure the membership was given

    # Member should not be able to add admin/owner/member
    add_permission_every_role(
        member_to_add=member_uname,
        member_requesting=member_session,
        create_res=create_res,
        host=host,
        view=view,
        datastore=datastore,
    )

    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner != member_uname
    assert member_uname not in view.admins

    # Member should not be able to remove admin/owner/member
    # adding owner into every role first
    add_permission_every_role(
        member_to_add=owner_uname,
        member_requesting=owner_session,
        create_res=create_res,
        host=host,
        view=view,
        datastore=datastore,
    )

    # verify owner is in every role
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner == owner_uname
    assert owner_uname in view.admins
    assert owner_uname in view.members

    # Unauthorized removal attempt by member
    remove_permission_every_role(
        member_to_remove=member_uname,
        member_requesting=member_session,
        create_res=create_res,
        host=host,
        view=view,
        datastore=datastore,
    )

    # ensure owner is still untouched in every role
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.owner == owner_uname
    assert owner_uname in view.admins
    assert owner_uname in view.members

    # Member should not be able to delete view
    total = datastore.view.search("view_id:*")["total"]
    with pytest.raises(APIError):
        get_api_data(
            member_session,
            f"{host}/api/v1/view/{create_res['view_id']}",
            method="DELETE",
        )

    assert total == datastore.view.search("view_id:*")["total"]  # Should not have deleted

    # Member should be able to update view
    modifying_view(member_requesting=member_session, create_res=create_res, host=host, view_name="MEMBER_CHANGED_NAME")
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.title == "MEMBER_CHANGED_NAME"

    return


# endregion
