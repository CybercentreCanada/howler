from requests import Session


def test_site_map(login_session: tuple[Session, str]):
    session, host = login_session
    data1 = session.get(f"{host}/api/site_map").json()["api_response"]
    assert isinstance(data1, list)

    data2 = session.get(f"{host}/api/site_map", params={"unsafe_only": "true"}).json()["api_response"]
    assert isinstance(data2, list)

    assert len(data1) > len(data2)
