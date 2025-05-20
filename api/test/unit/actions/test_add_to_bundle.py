import pytest

from howler.actions.add_to_bundle import execute
from howler.common import loader
from howler.common.loader import datastore
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_hit
from howler.odm.models.hit import Hit
from howler.odm.random_data import wipe_hits
from howler.odm.randomizer import random_model_obj
from howler.services import hit_service


@pytest.fixture(scope="module", autouse=True)
def setup_datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        datastore_connection.hit.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)


def test_execute_no_bundle_id():
    result = execute("howler.id:*", "not_a_valid_id")

    assert len(result) == 1

    result = result[0]

    assert result["outcome"] == "error"
    assert result["title"] == "Invalid Bundle"
    assert result["message"] == "Either a hit with ID not_a_valid_id does not exist, or it is not a bundle."
    assert result["message"] == "Either a hit with ID not_a_valid_id does not exist, or it is not a bundle."


def test_execute():
    bundle: Hit = random_model_obj(Hit)
    bundle.howler.is_bundle = True
    bundle.howler.hits = []
    datastore().hit.save(bundle.howler.id, bundle)

    for i in range(3):
        hit: Hit = random_model_obj(Hit)
        hit.howler.analytic = "TestingAddToBundle"
        if i == 0:
            hit.howler.is_bundle = True
        elif i == 1:
            hit.howler.is_bundle = False
            hit.howler.bundles = [bundle.howler.id]
            bundle.howler.hits.append(hit.howler.id)
        else:
            hit.howler.is_bundle = False
            hit.howler.bundles = []
        datastore().hit.save(hit.howler.id, hit)

    datastore().hit.commit()

    result = execute("howler.analytic:TestingAddToBundle", bundle.howler.id)

    assert len(result) == 3

    assert result[0]["outcome"] == "skipped"
    assert result[0]["title"] == "Skipped Bundles"
    assert result[0]["query"] == "(howler.analytic:TestingAddToBundle) AND howler.is_bundle:true"
    assert result[0]["message"] == "Bundles cannot be added to a bundle."

    assert result[1]["outcome"] == "skipped"
    assert result[1]["title"] == "Skipped Hits"
    assert result[1]["query"] == f"(howler.analytic:TestingAddToBundle) AND (howler.bundles:{bundle.howler.id})"
    assert result[1]["message"] == "These hits have already been added to the specified bundle."

    assert result[2]["outcome"] == "success"
    assert result[2]["title"] == "Executed Successfully"
    assert result[2]["message"] == "The specified bundle has had all matching hits added."


def test_execute_failed():
    lookups = loader.get_lookups()
    users = datastore().user.search("*:*")["items"]
    bundle: Hit = generate_useful_hit(lookups, [user["uname"] for user in users], prune_hit=True)
    bundle.howler.is_bundle = True
    bundle.howler.hits = []
    datastore().hit.save(bundle.howler.id, bundle)

    result = execute("howler.analytic:T^R&*H%^J&G%^E", bundle.howler.id)

    assert len(result) == 1
    result = result[0]

    assert result["outcome"] == "error"
    assert result["title"] == "Failed to Execute"
    assert "Failed to parse query " in result["message"]


def test_get_bundle_size():
    lookups = loader.get_lookups()
    users = datastore().user.search("*:*")["items"]
    hit_1: Hit = generate_useful_hit(lookups, [user["uname"] for user in users])
    hit_1.howler.analytic = "TestingBundleSize"
    hit_1.howler.is_bundle = False
    datastore().hit.save(hit_1.howler.id, hit_1)

    hit_2: Hit = generate_useful_hit(lookups, [user["uname"] for user in users])
    hit_2.howler.analytic = "TestingBundleSize"
    hit_2.howler.is_bundle = False
    datastore().hit.save(hit_2.howler.id, hit_2)

    hit_3: Hit = generate_useful_hit(lookups, [user["uname"] for user in users])
    hit_3.howler.analytic = "TestingBundleSize"
    hit_3.howler.is_bundle = False
    datastore().hit.save(hit_3.howler.id, hit_3)

    bundle_1: Hit = generate_useful_hit(lookups, [user["uname"] for user in users])
    bundle_1.howler.is_bundle = True
    bundle_1.howler.hits = [hit_1.howler.id]
    bundle_1.howler.bundle_size = 1
    datastore().hit.save(bundle_1.howler.id, bundle_1)
    datastore().hit.commit()

    execute("howler.analytic:TestingBundleSize", bundle_1.howler.id)

    bundle_hit = hit_service.get_hit(bundle_1.howler.id, as_odm=True)

    assert bundle_hit.howler.bundle_size == 3
