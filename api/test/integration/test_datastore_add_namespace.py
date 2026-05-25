import logging
import os
import time

import pytest

from howler import odm
from howler.datastore.collection import logger
from howler.odm.helper import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_hits

logger.setLevel(logging.INFO)
yml_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "classification.yml")


@odm.model(index=True, store=True)
class ExtensionModel(odm.Model):
    integer = odm.Integer(default=1)
    keyword = odm.Keyword(default="keyword")
    boolean = odm.Boolean(default=True)
    date = odm.Date(default="NOW")


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    ds = datastore_connection

    try:
        create_hits(ds, hit_count=10)
        ds.hit.model_class.add_namespace("example", odm.Compound(ExtensionModel))
        create_hits(ds, hit_count=10)

        ds.hit.commit()

        time.sleep(1)

        yield ds
    finally:
        ds.hit.model_class.remove_namespace("example")
        wipe_hits(ds)


def test_get_namespace_field(datastore):
    results = datastore.hit.search("example.keyword:*", fl="example.keyword")

    assert len(results["items"]) == 10

    for hit in results["items"]:
        assert isinstance(hit.example.keyword, str)


def test_get_index_mapping(datastore):
    index_mapping = datastore.hit._get_index_mappings()

    key_list = list(index_mapping["properties"].keys())

    assert "example.integer" in key_list
    assert "example.keyword" in key_list
    assert "example.boolean" in key_list
    assert "example.date" in key_list

    assert index_mapping["properties"]["example.integer"]["type"] == "integer"
    assert index_mapping["properties"]["example.keyword"]["type"] == "keyword"
    assert index_mapping["properties"]["example.boolean"]["type"] == "boolean"
    assert index_mapping["properties"]["example.date"]["type"] == "date"
