import logging
import os
import random
import string
import warnings
from typing import Annotated

import pytest
from datemath import dm
from pydantic import Field
from retrying import retry

from howler.datastore.collection import logger
from howler.datastore.exceptions import SearchException
from howler.models import HowlerEmbeddedModel, HowlerESModel, fields, keyword, mapping, model_registry, register_model
from howler.models.schema import document_mapping, index_settings

logger.setLevel(logging.INFO)
yml_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "classification.yml")


@register_model(index=True, store=True, embedded=True)
class ThingsModel(HowlerEmbeddedModel):
    count: fields.integer()
    thing: fields.text()


@register_model(index=True, store=True, embedded=True)
class MeasurementModel(HowlerEmbeddedModel):
    depth: fields.integer()
    width: fields.integer()


@register_model(index=True, store=True, embedded=True)
class Position(HowlerEmbeddedModel):
    x: fields.integer()
    y: fields.integer()


@register_model(index=True, store=True)
class BaseTestModel(HowlerESModel):
    classification: fields.classification(default="UNRESTRICTED", yml_config=yml_config)
    flavour: fields.text(copyto="features", default="EMPTY")
    height: fields.integer()
    no_store: fields.keyword(store=False, optional=True)
    no_index: fields.keyword(index=False, store=False, optional=True)
    dots: fields.mapping(Position, default={})
    birthday: fields.date()
    tags: Annotated[list[fields.enum({"silly", "cats", "10"})], fields.metadata(copyto="features")] = []
    size: Annotated[MeasurementModel, Field(default={"depth": 100, "width": 100})]
    features: list[fields.text()] = []
    metadata: fields.mapping(fields.text(), default={})
    things: list[ThingsModel] = []


def safe_date(pattern):
    return dm(f"{pattern}/m").isoformat().replace("+00:00", ".001Z")


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    test_map = {
        "test1": BaseTestModel.model_validate(
            dict(
                tags=["silly"],
                flavour="chocolate",
                height=100,
                birthday=safe_date("now-2d"),
                metadata={"url": "google.com"},
                things=[{"count": 1, "thing": "hat"}],
                classification="RESTRICTED",
            )
        ),
        "test2": BaseTestModel.model_validate(
            dict(
                tags=["cats"],
                flavour="A little dry",
                height=180,
                birthday=safe_date("now-1d"),
                metadata={"url": "google.ca"},
            )
        ),
        "test3": BaseTestModel.model_validate(
            dict(
                tags=["silly"],
                flavour="Red",
                height=140,
                birthday=safe_date("now"),
                size={"depth": 1, "width": 1},
                things=[{"count": 1, "thing": "hat"}, {"count": 10, "thing": "shoe"}],
                classification="RESTRICTED",
            )
        ),
        "test4": BaseTestModel.model_validate(
            dict(
                tags=["cats"],
                flavour="Bugs ++",
                height=30,
                birthday="2018-10-30T17:48:48.123Z",
            )
        ),
        "dict1": BaseTestModel.model_validate(
            dict(
                tags=["cats"],
                flavour="A--",
                height=300,
                birthday="2018-10-30T17:48:48.123Z",
            )
        ),
        "dict2": BaseTestModel.model_validate(
            dict(
                tags=[],
                flavour="100%",
                height=90,
                birthday=safe_date("now"),
                metadata={"origin": "space"},
            )
        ),
        "dict3": BaseTestModel.model_validate(
            dict(
                tags=["10", "cats"],
                flavour="",
                height=180,
                birthday=safe_date("now-3d"),
                classification="RESTRICTED",
            )
        ),
        "dict4": BaseTestModel.model_validate(
            dict(
                tags=["10", "silly", "cats"],
                flavour="blue",
                height=100,
                birthday=safe_date("now-1d"),
            )
        ),
        "extra1": BaseTestModel.model_validate(
            dict(
                tags=["10"],
                flavour="delicious",
                height=300,
                birthday=safe_date("now-1h"),
                no_index="nidx1",
                no_store="nsto1",
                dots={"first": {"x": 111, "y": 222}},
            )
        ),
        "extra2": BaseTestModel.model_validate(
            dict(
                tags=["silly", "10"],
                flavour="delicious",
                height=400,
                birthday=safe_date("now-2h"),
                no_index="nidx2",
                no_store="nsto2",
            )
        ),
        "extra3": BaseTestModel.model_validate(
            dict(
                tags=["10", "silly", "cats"],
                flavour="delicious",
                height=500,
                birthday=safe_date("now-3h"),
                no_index="nidx3",
                no_store="nsto3",
                dots={"first": {"x": 123, "y": 456}, "second": {"x": 222, "y": 333}},
            )
        ),
        "extra4": BaseTestModel.model_validate(
            dict(
                tags=["cats"],
                flavour="delicious",
                height=600,
                birthday=safe_date("now-4h"),
                no_index="nidx4",
                no_store="nsto4",
            )
        ),
    }


class SetupException(Exception):
    pass


@retry(stop_max_attempt_number=10, wait_random_min=100, wait_random_max=500)
def setup_store(docstore, request):
    try:
        ret_val = docstore.ping()
        if ret_val:
            collection_name = "".join(random.choices(string.ascii_lowercase, k=10))
            docstore.register(collection_name, BaseTestModel)
            collection = docstore.__getattr__(collection_name)
            request.addfinalizer(collection.wipe)

            # cleanup
            for k in test_map.keys():
                collection.delete(k)

            for k, v in test_map.items():
                collection.save(k, v)

            # Commit saved data
            collection.commit()

            return collection
    except ConnectionError:
        pass
    raise SetupException("Could not setup Datastore: %s" % docstore.__class__.__name__)


@pytest.fixture(scope="module")
def es_store():
    from howler.datastore.store import ESStore

    store = ESStore()
    ret_val = store.ping()
    if ret_val:
        return store

    return pytest.skip("Connection to the Elasticsearch server failed. This test cannot be performed.")


@pytest.fixture(scope="module")
def es_connection(es_store, request):
    try:
        collection = setup_store(es_store, request)
    except SetupException:
        collection = None

    if collection:
        return collection

    return pytest.skip("Connection to the Elasticsearch server failed. This test cannot be performed.")


def get_obj(obj_map, key, as_obj):
    obj = obj_map.get(key)
    if not as_obj:
        return obj.as_primitives()
    return obj


def document_data(value):
    """Compare document content independently of Elasticsearch response metadata."""
    return value.as_primitives() if isinstance(value, HowlerESModel) else value


def _test_exists(col, _):
    assert not col.exists("not-a-key")

    for x in range(1, 4):
        assert col.exists(f"test{x}")

    for x in range(1, 4):
        assert col.exists(f"dict{x}")

    for x in range(1, 4):
        assert col.exists(f"extra{x}")

    assert not col.exists("string")
    assert not col.exists("list")
    assert not col.exists("int")


def _test_get(col, as_obj):
    assert col.get("not-a-key", as_obj=as_obj) is None
    assert col.get_if_exists("not-a-key", as_obj=as_obj) is None

    for x in range(1, 4):
        assert document_data(get_obj(test_map, f"test{x}", as_obj)) == document_data(col.get(f"test{x}", as_obj=as_obj))

    for x in range(1, 4):
        assert document_data(get_obj(test_map, f"dict{x}", as_obj)) == document_data(
            col.get_if_exists(f"dict{x}", as_obj=as_obj)
        )

    for x in range(1, 4):
        assert document_data(get_obj(test_map, f"extra{x}", as_obj)) == document_data(
            col.require(f"extra{x}", as_obj=as_obj)
        )

    assert col.get("string", as_obj=as_obj) is None
    assert col.get("list", as_obj=as_obj) is None
    assert col.get("int", as_obj=as_obj) is None


def _test_get_primitives(col, _):
    # Test is as_obj=False is equivalent to as_primitives function
    assert col.get("test1", as_obj=False) == col.get("test1").as_primitives()


def _test_mget(col, as_obj):
    raw = [
        get_obj(test_map, "test1", as_obj),
        get_obj(test_map, "dict1", as_obj),
        get_obj(test_map, "test2", as_obj),
        get_obj(test_map, "extra3", as_obj),
    ]
    ds_raw = col.multiget(["test1", "dict1", "test2", "extra3"], as_dictionary=False, as_obj=as_obj)
    raw = [document_data(item) for item in raw]
    for item in ds_raw:
        raw.remove(document_data(item))
    assert len(raw) == 0

    for k, v in col.multiget(["test1", "dict1", "test2", "extra3"], as_obj=as_obj).items():
        assert document_data(get_obj(test_map, k, as_obj)) == document_data(v)

    with pytest.raises(KeyError) as error_info:
        col.multiget(["not-a-key-1", "not-a-key-2"], as_obj=as_obj)
    assert "not-a-key" in str(error_info.value)


def _test_keys(col, _):
    test_keys = list(test_map.keys())
    for k in col.keys():
        test_keys.remove(k)
    assert len(test_keys) == 0


def _test_search(col, as_obj):
    t1 = col.search("*:*", sort="id asc", as_obj=as_obj)
    assert len(t1["items"]) == t1["total"]

    # reading list fields on a search
    t2 = col.search("id:dict3", as_obj=as_obj)["items"][0]
    t3 = col.search("id:dict4", as_obj=as_obj)["items"][0]
    if as_obj:
        assert len(t2.tags) == 2
        assert len(t3.tags) == 3
    else:
        assert len(t2["tags"]) == 2
        assert len(t3["tags"]) == 3

    # reading single fields on a search
    t4 = col.search("id:test1", as_obj=as_obj)["items"][0]
    if as_obj:
        assert t4.flavour == "chocolate"
    else:
        assert t4["flavour"] == "chocolate"

    # Make sure sorting on the ID key works right
    forward = col.search("*", sort="id asc", as_obj=as_obj)
    reverse = col.search("*", sort="id desc", as_obj=as_obj)
    assert forward["items"] == list(reversed(reverse["items"]))

    # Search on a copyto field
    assert col.search("features:chocolate", as_obj=as_obj)["total"] == 1

    # Make sure we are getting only the expected fields with a field list
    result = col.search("features:chocolate", fl="features", as_obj=as_obj)
    assert result["total"] == 1
    if as_obj:
        assert "flavour" not in result["items"][0].model_fields_set
    else:
        with pytest.raises(KeyError):
            _ = result["items"][0]["flavour"]

    # Check that the metadata is searchable
    assert col.search("metadata.url:*google*", as_obj=as_obj)["total"] == 2
    assert col.search("classification:RESTRICTED", as_obj=as_obj)["total"] == 3

    # Testing non indexed and non stored fields
    try:
        res = col.search("no_index:nidx*", as_obj=as_obj)
    except SearchException:
        res = {"total": 0}

    assert res["total"] == 0
    assert col.search("no_store:nsto*", as_obj=as_obj)["total"] == 4


def _test_groupsearch(col, as_obj):
    g_res = col.grouped_search("height", fl="flavour", as_obj=as_obj)
    assert g_res["total"] == 12
    assert len(g_res["items"]) <= g_res["rows"]
    total = 0
    for item in g_res["items"]:
        assert "value" in item
        assert isinstance(item["value"], int)
        assert "total" in item
        assert isinstance(item["total"], int)
        assert "items" in item
        assert isinstance(item["items"], list)

        total += item["total"]
        assert 1 <= len(item["items"]) <= item["total"]

        if as_obj:
            assert isinstance(item["items"][0].flavour, str)
        else:
            assert isinstance(item["items"][0]["flavour"], str)

    assert total == g_res["total"]


def _test_search_primitives(col, _):
    # Make sure as_obj=False produces the same result then obj.as_primitives()
    obj_item = col.search("features:chocolate", fl="flavour")["items"][0]
    dict_item = col.search("features:chocolate", fl="flavour", as_obj=False)["items"][0]
    assert obj_item.as_primitives() == dict_item
    assert dict_item.get("flavour", None) == "chocolate"


def _test_streamsearch(col, as_obj):
    res = col.search("flavour:*", filters="height:[30 TO 400]", fl="flavour", as_obj=as_obj)
    items = list(col.stream_search("flavour:*", filters="height:[30 TO 400]", fl="flavour", as_obj=as_obj))
    assert len(items) == res["total"]
    for item in items:
        assert item in res["items"]


def _test_histogram(col, _):
    h_int = col.histogram("height", 0, 200, 20, mincount=2)
    for k, v in h_int.items():
        assert isinstance(k, int)
        assert isinstance(v, int)
        assert v > 0

    h_date = col.histogram(
        "birthday",
        "{n}-10{d}/{d}".format(n=col.datastore.now, d=col.datastore.day),
        "{n}+10{d}/{d}".format(n=col.datastore.now, d=col.datastore.day),
        "+1{d}".format(d=col.datastore.day),
        mincount=2,
    )
    for k, v in h_date.items():
        assert isinstance(k, str)
        assert "T00:00:00" in k
        assert k.endswith("Z")
        assert isinstance(v, int)
        assert v > 0


def _test_facet(col, _):
    facets = col.facet("tags")
    for k, v in facets.items():
        assert k in ["cats", "10", "silly"]
        assert isinstance(v, int)
        assert v > 0


def _test_stats(col, _):
    stats = col.stats("height")
    for k, v in stats.items():
        assert k in ["count", "min", "max", "avg", "sum"]
        assert isinstance(v, (int, float))
        assert v > 0


def _test_fields(col, _):
    db_fields = col.fields()
    model_fields = model_registry.flat_fields(BaseTestModel)
    properties = document_mapping(BaseTestModel)["properties"]
    for k, v in model_fields.items():
        if v.metadata is not None and v.metadata.kind == "Mapping":
            continue
        else:
            assert db_fields[k]["type"] == properties[k]["type"]


TEST_FUNCTIONS = [
    (_test_exists, None, "exists - object"),
    (_test_get, True, "get - object"),
    (_test_get, False, "get - dict"),
    (_test_get_primitives, None, "get primitives"),
    (_test_mget, True, "multiget - object"),
    (_test_mget, False, "multiget - dict"),
    (_test_keys, None, "keys"),
    (_test_search, True, "search - object"),
    (_test_search, False, "search - dict"),
    (_test_groupsearch, True, "groupsearch - object"),
    (_test_groupsearch, False, "groupsearch - dict"),
    (_test_search_primitives, None, "search primitives"),
    (_test_streamsearch, True, "streamsearch - object"),
    (_test_streamsearch, False, "streamsearch - dict"),
    (_test_histogram, None, "histogram"),
    (_test_facet, None, "facet"),
    (_test_stats, None, "stats"),
    (_test_fields, None, "fields"),
]


# noinspection PyShadowingNames
@pytest.mark.parametrize(
    "function,as_obj",
    [(f[0], f[1]) for f in TEST_FUNCTIONS],
    ids=[f[2] for f in TEST_FUNCTIONS],
)
def test_es(es_connection, function, as_obj):
    function(es_connection, as_obj)


def test_dynamic_fields(es_store, request):
    @register_model(index=True, store=True)
    class Test(HowlerESModel):
        number: fields.integer()
        other: fields.any_field(index=False)

    collection_name = "".join(random.choices(string.ascii_lowercase, k=10))
    es_store.register(collection_name, Test)
    col = getattr(es_store, collection_name)
    request.addfinalizer(col.wipe)
    col.wipe()

    assert list(sorted(col.fields().keys())) == ["number", "other"]

    # Elasticsearch should ignore the type of other
    data = {
        "int": Test(number=100, other=100),
        "str": Test(number=100, other="100"),
        "bool": Test(number=100, other=True),
    }

    for k, v in data.items():
        col.save(k, v)

    for k in data.keys():
        assert col.get(k).as_primitives() == data[k].as_primitives()


@register_model(index=True, store=True, id_field="key")
class LiveReconcileDoc(HowlerESModel):
    """A compact schema used to verify live index field discovery and reconciliation."""

    key: keyword()
    name: keyword(description="A plain, statically typed field.")
    tags: mapping(keyword(), default={}, description="A dynamic-key mapping field.")


def _random_schema_collection_name() -> str:
    return "schematest_" + "".join(random.choices(string.ascii_lowercase, k=8))


@pytest.fixture()
def schema_collection(es_store, request):
    name = _random_schema_collection_name()
    es_store.register(name, model_class=LiveReconcileDoc)
    collection = getattr(es_store, name)

    def cleanup():
        try:
            collection.datastore.client.indices.delete(index=f"{collection.name}_hot", ignore_unavailable=True)
        except Exception:
            logger.exception("Failed to clean up schema test collection %r", name)

    request.addfinalizer(cleanup)
    return collection


def test_new_collection_has_expected_index_mapping(schema_collection):
    client = schema_collection.datastore.client
    live = client.indices.get(index=schema_collection.name)
    live_index = next(iter(live.values()))

    expected_settings = index_settings(
        LiveReconcileDoc,
        shards=schema_collection.shards,
        replicas=schema_collection.replicas,
    )
    live_settings = live_index["settings"]["index"]
    assert int(live_settings["number_of_shards"]) == expected_settings["index"]["number_of_shards"]
    assert (
        int(live_settings["mapping"]["total_fields"]["limit"])
        == expected_settings["index"]["mapping"]["total_fields"]["limit"]
    )

    expected_mappings = document_mapping(LiveReconcileDoc)
    live_properties = live_index["mappings"]["properties"]
    assert set(live_properties) == set(expected_mappings["properties"])
    for field_name, expected_body in expected_mappings["properties"].items():
        assert live_properties[field_name].get("type") == expected_body.get("type"), field_name
        if "enabled" in expected_body:
            assert live_properties[field_name].get("enabled", True) == expected_body["enabled"], field_name

    live_template_keys = {next(iter(template)) for template in live_index["mappings"]["dynamic_templates"]}
    expected_template_keys = {next(iter(template)) for template in expected_mappings["dynamic_templates"]}
    assert live_template_keys == expected_template_keys


def test_fields_include_live_dynamic_mapping_children(schema_collection):
    schema_collection.save("doc1", {"key": "doc1", "name": "hello", "tags": {"env": "prod"}})
    schema_collection.commit()

    fields_map = schema_collection.fields()

    assert fields_map["name"]["type"] == "keyword"
    assert fields_map["name"]["description"] == "A plain, statically typed field."
    assert fields_map["tags"]["description"] == "A dynamic-key mapping field."
    assert "tags.env" in fields_map


def test_reconciliation_adds_missing_safe_fields_to_a_live_index(es_store):
    from howler.common.loader import DATASTORE_INDEX_PREFIX

    name = _random_schema_collection_name()
    mappings = document_mapping(LiveReconcileDoc)
    mappings["properties"] = {key: value for key, value in mappings["properties"].items() if key != "name"}
    settings = index_settings(LiveReconcileDoc, shards=1, replicas=0)
    index_name = f"{DATASTORE_INDEX_PREFIX}-{name}"
    es_store.client.indices.create(
        index=f"{index_name}_hot",
        mappings=mappings,
        settings=settings,
        aliases={index_name: {}},
    )

    try:
        es_store.register(name, model_class=LiveReconcileDoc)
        collection = getattr(es_store, name)
        fields_map = collection.fields()

        assert fields_map["name"]["type"] == "keyword"
        live = es_store.client.indices.get(index=f"{index_name}_hot")
        assert "name" in next(iter(live.values()))["mappings"]["properties"]
    finally:
        es_store.client.indices.delete(index=f"{index_name}_hot", ignore_unavailable=True)


def test_reconciliation_refuses_a_missing_dynamic_template(es_store):
    from howler.common.exceptions import HowlerValueError
    from howler.common.loader import DATASTORE_INDEX_PREFIX

    name = _random_schema_collection_name()
    mappings = document_mapping(LiveReconcileDoc)
    mappings["dynamic_templates"] = [
        template for template in mappings["dynamic_templates"] if next(iter(template)) != "tags.*_tpl"
    ]
    settings = index_settings(LiveReconcileDoc, shards=1, replicas=0)
    index_name = f"{DATASTORE_INDEX_PREFIX}-{name}"
    es_store.client.indices.create(
        index=f"{index_name}_hot",
        mappings=mappings,
        settings=settings,
        aliases={index_name: {}},
    )

    try:
        es_store.register(name, model_class=LiveReconcileDoc)
        with pytest.raises(HowlerValueError, match="Refusing to add or change dynamic mapping templates"):
            getattr(es_store, name)
    finally:
        es_store.client.indices.delete(index=f"{index_name}_hot", ignore_unavailable=True)
