import pytest
from mergedeep.mergedeep import merge

from howler.common.exceptions import ForbiddenException, NotFoundException
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_dossier
from howler.odm.models.dossier import Dossier
from howler.odm.random_data import create_dossiers, wipe_dossiers
from howler.security import InvalidDataException
from howler.services import dossier_service


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_dossiers(ds, num_dossiers=10)

        yield ds
    finally:
        wipe_dossiers(ds)


def test_exists(datastore: HowlerDatastore):
    existing_dossier_id = datastore.dossier.search("dossier_id:*", as_obj=True)["items"][0].dossier_id

    assert dossier_service.exists(existing_dossier_id)


def test_get_dossier(datastore: HowlerDatastore):
    existing_dossier_id = datastore.dossier.search("dossier_id:*", as_obj=True)["items"][0].dossier_id

    assert dossier_service.get_dossier(existing_dossier_id, as_odm=True).dossier_id == existing_dossier_id


def test_create_dossier(datastore: HowlerDatastore):
    users = datastore.user.search("uname:*")["items"]

    result = dossier_service.create_dossier(generate_useful_dossier(users).as_primitives(), username="admin")

    assert len(result.leads) > 0
    assert len(result.leads) < 4


def test_create_dossier_fails(datastore: HowlerDatastore):
    users = datastore.user.search("uname:*")["items"]

    example = generate_useful_dossier(users).as_primitives()

    with pytest.raises(InvalidDataException):
        dossier_service.create_dossier([], username="admin")

    with pytest.raises(InvalidDataException):
        bad_example = merge({}, example)
        del bad_example["title"]
        dossier_service.create_dossier(bad_example, username="admin")

    with pytest.raises(InvalidDataException):
        bad_example = merge({}, example)
        bad_example["query"] = "adjigvq34b895734no787888907089%^&%^&*%^&*%^&*%^&*kmlml,;;l,.[]"
        dossier_service.create_dossier(bad_example, username="admin")


def test_update_dossier_fails(datastore: HowlerDatastore):
    user = datastore.user.search("uname:admin")["items"][0]

    with pytest.raises(NotFoundException):
        dossier_service.update_dossier("potatopotatopotato", {"owner": "test"}, user).owner == "test"

    existing_dossier: Dossier = datastore.dossier.search("type:personal", as_obj=True)["items"][0]

    with pytest.raises(ForbiddenException):
        other_user = datastore.user.search(f"-uname:{existing_dossier.owner} AND -type:admin")["items"][0]
        dossier_service.update_dossier(existing_dossier.dossier_id, {"owner": other_user.uname}, other_user)

    existing_dossier = datastore.dossier.search("type:global", as_obj=True)["items"][0]
    with pytest.raises(ForbiddenException):
        other_user = datastore.user.search(f"-uname:{existing_dossier.owner} AND -type:admin")["items"][0]
        dossier_service.update_dossier(existing_dossier.dossier_id, {"owner": other_user.uname}, other_user)

    user = datastore.user.search(f"uname:{existing_dossier.owner}")["items"][0]
    with pytest.raises(InvalidDataException):
        dossier_service.update_dossier(
            existing_dossier.dossier_id, {"query": "sdklfjnasdvrtvybnuiseybuniosertv897890['['[/]['/]"}, user
        )

    with pytest.raises(InvalidDataException) as exc:
        dossier_service.update_dossier(existing_dossier.dossier_id, {"test": "TEST"}, user)

    assert exc.match("can be updated")


def test_update_dossier(datastore: HowlerDatastore):
    user = datastore.user.search("uname:admin")["items"][0]
    existing_dossier_id = datastore.dossier.search("type:global", as_obj=True)["items"][0].dossier_id

    assert dossier_service.update_dossier(existing_dossier_id, {"owner": "test"}, user).owner == "test"


def test_pivot_with_duplicates(datastore: HowlerDatastore):
    users = datastore.user.search("uname:*")["items"]

    dossier_odm = generate_useful_dossier(users)
    dossier_odm.pivots[0].mappings.append(dossier_odm.pivots[0].mappings[0])

    dossier = dossier_odm.as_primitives()

    with pytest.raises(InvalidDataException):
        dossier_service.create_dossier(dossier, username="admin")
