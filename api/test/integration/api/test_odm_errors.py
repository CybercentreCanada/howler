import json

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore

invalid_hit = {
    "howler": {
        "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc",
    },
}


def test_odm_errors(datastore_connection: HowlerDatastore, login_session):
    """Test that /api/v1/hit/<id>/transitions/start endpoint performs the correct transition"""
    session, host = login_session

    with pytest.raises(APIError) as excinfo:
        get_api_data(
            session=session,
            url=f"{host}/api/v1/hit/",
            data=json.dumps([invalid_hit]),
            method="POST",
        )

    res = excinfo.value.json["api_response"]

    assert len(res["invalid"]) == 1
    assert res["invalid"][0]["error"].startswith("[hit.howler.analytic]")

    invalid_hit["howler"]["analytic"] = "odm-error-test"

    invalid_hit["howler"]["score"] = "shouldnt be a string"

    with pytest.raises(APIError) as excinfo:
        get_api_data(
            session=session,
            url=f"{host}/api/v1/hit/",
            data=json.dumps([invalid_hit]),
            method="POST",
        )

    res = excinfo.value.json["api_response"]

    assert len(res["invalid"]) == 1
    assert res["invalid"][0]["error"].startswith("[hit.howler.score]")

    invalid_hit["howler"]["score"] = 1234.5678

    res = get_api_data(
        session=session,
        url=f"{host}/api/v1/hit/",
        data=json.dumps([invalid_hit]),
        method="POST",
    )

    assert len(res["valid"]) == 1

    invalid_hit["destination"] = {"bytes": "shouldnt be a string"}

    with pytest.raises(APIError) as excinfo:
        get_api_data(
            session=session,
            url=f"{host}/api/v1/hit/",
            data=json.dumps([invalid_hit]),
            method="POST",
        )

    res = excinfo.value.json["api_response"]

    assert len(res["invalid"]) == 1
    assert res["invalid"][0]["error"].startswith("[hit.destination.bytes]")

    invalid_hit.pop("destination")
    invalid_hit["howler"]["hash"] = ""

    with pytest.raises(APIError) as excinfo:
        get_api_data(
            session=session,
            url=f"{host}/api/v1/hit/",
            data=json.dumps([invalid_hit]),
            method="POST",
        )

    res = excinfo.value.json["api_response"]

    assert len(res["invalid"]) == 1
    assert res["invalid"][0]["error"].startswith("[hit.howler.hash]")

    invalid_hit["howler"]["hash"] = "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc"

    res = get_api_data(
        session=session,
        url=f"{host}/api/v1/hit/",
        data=json.dumps([invalid_hit]),
        method="POST",
    )

    assert len(res["valid"]) == 1
