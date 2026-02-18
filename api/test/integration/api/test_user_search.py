import json

import pytest
from conftest import APIError, get_api_data

from howler.odm.random_data import create_users, wipe_users


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        wipe_users(ds)
        create_users(ds)
        yield ds
    finally:
        wipe_users(ds)
        create_users(ds)


def _collect_password_values(data):
    values = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "password":
                values.append(value)
            values.extend(_collect_password_values(value))
    elif isinstance(data, list):
        for item in data:
            values.extend(_collect_password_values(item))

    return values


def _assert_not_allowed_error(error: APIError):
    assert str(error).startswith("400") or str(error).startswith("403")


def _assert_no_sensitive_user_leak(item: dict, stored_user: dict):
    expected_hashes = {stored_user.get("password")}
    expected_hashes |= {
        api_key_data.get("password")
        for api_key_data in stored_user.get("apikeys", {}).values()
        if isinstance(api_key_data, dict)
    }
    expected_hashes.discard(None)

    leaked_password_values = set(_collect_password_values(item))

    for key, value in item.items():
        if key.endswith(".password"):
            leaked_password_values.add(value)

    assert leaked_password_values.isdisjoint(expected_hashes)


def _build_fl(stored_user: dict):
    fields = ["uname", "password", "apikeys"]
    apikeys = stored_user.get("apikeys", {})

    if apikeys:
        fields.extend([f"apikeys.{key_name}.password" for key_name in apikeys])
    else:
        fields.append("apikeys.devkey.password")

    return ",".join(fields)


def _assert_no_facet_leak(facet_response: dict, stored_user: dict):
    expected_hashes = {stored_user.get("password")}
    expected_hashes |= {
        api_key_data.get("password")
        for api_key_data in stored_user.get("apikeys", {}).values()
        if isinstance(api_key_data, dict)
    }
    expected_hashes.discard(None)

    assert set(facet_response.keys()).isdisjoint(expected_hashes)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_search_get(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    params = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": _build_fl(stored_user),
    }

    try:
        response = get_api_data(session, f"{host}/api/v1/search/user/", params=params)
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("uname") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_search_post(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    body = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": _build_fl(stored_user),
    }

    try:
        response = get_api_data(
            session,
            f"{host}/api/v1/search/user/",
            method="POST",
            data=json.dumps(body),
        )
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("uname") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_search_get_fl_wildcard(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    params = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": "*",
    }

    try:
        response = get_api_data(session, f"{host}/api/v1/search/user/", params=params)
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("uname") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_search_post_fl_wildcard(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    body = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": "*",
    }

    try:
        response = get_api_data(
            session,
            f"{host}/api/v1/search/user/",
            method="POST",
            data=json.dumps(body),
        )
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("uname") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_grouped_search_get(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    params = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": _build_fl(stored_user),
    }

    try:
        response = get_api_data(session, f"{host}/api/v1/search/grouped/user/uname/", params=params)
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("value") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_grouped_search_post(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    body = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": _build_fl(stored_user),
    }

    try:
        response = get_api_data(
            session,
            f"{host}/api/v1/search/grouped/user/uname/",
            method="POST",
            data=json.dumps(body),
        )
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("value") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_grouped_search_get_fl_wildcard(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    params = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": "*",
    }

    try:
        response = get_api_data(session, f"{host}/api/v1/search/grouped/user/uname/", params=params)
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("value") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_grouped_search_post_fl_wildcard(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    body = {
        "query": f'uname:"{username}"',
        "rows": 1000,
        "fl": "*",
    }

    try:
        response = get_api_data(
            session,
            f"{host}/api/v1/search/grouped/user/uname/",
            method="POST",
            data=json.dumps(body),
        )
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    matching_users = [item for item in response.get("items", []) if item.get("value") == username]
    assert matching_users

    for item in matching_users:
        _assert_no_sensitive_user_leak(item, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_facet_field_password_get(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    params = {"query": f'uname:"{username}"'}

    try:
        response = get_api_data(session, f"{host}/api/v1/search/facet/user/password/", params=params)
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    _assert_no_facet_leak(response, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_facet_field_password_post(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    body = {"query": f'uname:"{username}"'}

    try:
        response = get_api_data(
            session,
            f"{host}/api/v1/search/facet/user/password/",
            method="POST",
            data=json.dumps(body),
        )
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    _assert_no_facet_leak(response, stored_user)


@pytest.mark.parametrize("username", ["admin", "user", "huey", "goose", "shawn-h"])
def test_sensitive_fields_not_exposed_in_user_facet_multi_field_post(datastore, login_session, username):
    session, host = login_session
    stored_user = datastore.user.get(username, as_obj=False)

    body = {
        "query": f'uname:"{username}"',
        "fields": ["password", "apikeys.devkey.password"],
    }

    try:
        response = get_api_data(
            session,
            f"{host}/api/v1/search/facet/user",
            method="POST",
            data=json.dumps(body),
        )
    except APIError as error:
        _assert_not_allowed_error(error)
        return

    for field in ["password", "apikeys.devkey.password"]:
        if field in response:
            _assert_no_facet_leak(response[field], stored_user)
