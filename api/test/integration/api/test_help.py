from conftest import get_api_data


# noinspection PyUnusedLocal
def test_classification_definition(datastore_connection, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/help/classification_definition/")
    assert isinstance(resp, dict)
