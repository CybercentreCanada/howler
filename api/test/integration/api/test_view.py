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

    assert all(t["type"] == "global" or t["owner"] in [["admin"], ["none"]] for t in resp)


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


def add_permission_every_role(member_to_add: str, member_requesting, create_res, host, view):
    try:
        for membership in view.get_privilege_mapping().keys():
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
    # Error is intended sometime.
    except APIError:
        return


def remove_permission_every_role(member_to_remove: str, member_requesting, create_res, host, view):
    try:
        for membership in view.get_privilege_mapping().keys():
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
    # Error is intended sometime.
    except APIError:
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
    view: View = datastore.view.get(create_res["view_id"], as_obj=True)

    # Give|Remove every possible membership
    for request in ("PUT", "DELETE"):
        for membership in view.get_privilege_mapping().keys():
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
            # updating the view for testing
            view: View = datastore.view.get(create_res["view_id"], as_obj=True)
            if request == "PUT":
                assert member_uname in view.get_privilege_mapping()[membership]
                continue
            assert member_uname not in view.get_privilege_mapping()[membership]

    # Delete the view
    get_api_data(owner_session, f"{host}/api/v1/view/{create_res['view_id']}/", method="DELETE")


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
    # adding|remove user to admin, member and owner
    add_permission_every_role(
        member_to_add=member_uname, create_res=create_res, member_requesting=owner_session, host=host, view=view
    )

    view = datastore.view.get(create_res["view_id"], as_obj=True)
    for membership in view.get_privilege_mapping().keys():
        assert member_uname in view.get_privilege_mapping()[membership]

    remove_permission_every_role(
        member_to_remove=member_uname, create_res=create_res, member_requesting=owner_session, host=host, view=view
    )

    view = datastore.view.get(create_res["view_id"], as_obj=True)
    for membership in view.get_privilege_mapping().keys():
        assert member_uname not in view.get_privilege_mapping()[membership]

    # Owner should be able to modify the view
    modifying_view(member_requesting=owner_session, create_res=create_res, host=host)
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.title == "renamed_view"

    # Owner should be able to delete the view
    # Create an other temporary view
    total = datastore.view.search("view_id:*")["total"]

    create_res_copy = get_api_data(
        owner_session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )
    datastore.view.commit()
    # Verify created properly
    assert total + 1 == datastore.view.search("view_id:*")["total"]

    # Giving ownership to an other user
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res_copy['view_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "privilege": "owner",
            }
        ),
    )
    datastore.view.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res_copy['view_id']}",
        method="DELETE",
    )
    datastore.view.commit()
    assert total == datastore.view.search("view_id:*")["total"]

    # Owner should be able to remove self if other owner exist
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
    get_api_data(
        owner_session,
        f"{host}/api/v1/view/{create_res['view_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": owner_uname,
                "privilege": "owner",
            }
        ),
    )
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert owner_uname not in view.get_privilege_mapping()["owner"]

    # Owner should not be able to remove self if no other owner exist
    try:
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
    except Exception:
        # The error is intentional
        pass

    datastore.view.commit()

    assert member_uname in view.get_privilege_mapping()["owner"]

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
                "privilege": "administrator",
            }
        ),
    )
    assert owner_uname not in view.get_privilege_mapping()["administrator"]  # ensure user is admin

    # Admin should be able to add|remove member and other admin
    for method in ["PUT", "DELETE"]:
        get_api_data(
            admin_session,
            f"{host}/api/v1/view/{create_res['view_id']}/permission",
            method=method,
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "privilege": "administrator",
                }
            ),
        )
        datastore.view.commit()
        view = datastore.view.get(create_res["view_id"], as_obj=True)
        if method == "PUT":
            assert member_uname in view.get_privilege_mapping()["administrator"]
            continue
        assert member_uname not in view.get_privilege_mapping()["administrator"]

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
    assert member_uname not in view.get_privilege_mapping()["owner"]
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
    assert admin_uname not in view.get_privilege_mapping()["owner"]

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
                "privilege": "administrator",
            }
        ),
    )
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert admin_uname not in view.get_privilege_mapping()["administrator"]
    assert view.get_privilege_mapping()["administrator"] == []

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
                "privilege": "member",
            }
        ),
    )
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert member_uname in view.get_privilege_mapping()["member"]  # ensure the membership was given

    # Member should not be able to add admin/owner/member
    add_permission_every_role(
        create_res=create_res, host=host, member_requesting=member_session, member_to_add=member_uname, view=view
    )
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    for membership in ["owner", "administrator"]:
        assert member_uname not in view.get_privilege_mapping()[membership]

    # Member should not be able to remove admin/owner/member
    # adding owner into every role
    add_permission_every_role(
        create_res=create_res, host=host, member_requesting=owner_session, member_to_add=owner_uname, view=view
    )
    # verify owner is in every role
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    for membership in view.get_privilege_mapping().keys():
        assert owner_uname in view.get_privilege_mapping()[membership]

    remove_permission_every_role(
        create_res=create_res, host=host, member_requesting=member_session, member_to_remove=member_uname, view=view
    )
    # ensure owner is still in every role
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    for membership in view.get_privilege_mapping().keys():
        assert owner_uname in view.get_privilege_mapping()[membership]
    # Member should not be able to delete view
    total = datastore.view.search("view_id:*")["total"]
    try:
        get_api_data(
            member_session,
            f"{host}/api/v1/view/{create_res['view_id']}",
            method="DELETE",
        )
    except Exception:
        # intended fail
        pass

    assert total == datastore.view.search("view_id:*")["total"]  # Should not have deleted

    # Member should be able to update view
    modifying_view(member_requesting=member_session, create_res=create_res, host=host, view_name="MEMBER_CHANGED_NAME")
    datastore.view.commit()
    view = datastore.view.get(create_res["view_id"], as_obj=True)
    assert view.title == "MEMBER_CHANGED_NAME"
    return


# endregion
