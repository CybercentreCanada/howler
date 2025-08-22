import json
from pathlib import Path

import pytest
from utils.queries import generate_lucene_query

from howler.common import loader
from howler.common.logging import get_logger
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_hit
from howler.odm.models.hit import Hit
from howler.services import lucene_service

logger = get_logger(__file__)


@pytest.fixture(scope="module")
def hit(datastore_connection):
    ds = datastore_connection

    hit_file_path = Path(__file__).parent / "hit.json"
    if not hit_file_path.exists():
        lookups = loader.get_lookups()
        users = ds.user.search("*:*")["items"]
        _hit = generate_useful_hit(lookups, [user["uname"] for user in users], prune_hit=False)

        with hit_file_path.open("w") as _file:
            json.dump(_hit.as_primitives(), _file)
    else:
        with hit_file_path.open("r") as _file:
            _hit = Hit(json.load(_file))

    return _hit


@pytest.fixture(scope="module")
def queries():
    queries_file_path = Path(__file__).parent / "test_queries.txt"

    _queries = queries_file_path.read_text().strip().split("\n")

    return [query for query in _queries if query and not query.startswith("#")]


@pytest.fixture(scope="module")
def datastore(datastore_connection, hit):
    ds = datastore_connection

    ds.hit.save(hit.howler.id, hit)

    ds.hit.commit()

    yield ds


def test_lucene_match(datastore: HowlerDatastore, hit, queries):
    data = hit.as_primitives()

    print("\n")  # noqa: T201
    logger.info("Executing saved test queries")
    for query in queries:
        assert lucene_service.match(query, data) == (
            datastore.hit.search(f"({query}) AND howler.id:{hit.howler.id}", rows=0)["total"] > 0
        )

    logger.info("Executing randomly generated test queries")
    for c in range(3):
        query = generate_lucene_query(data, complexity=c * 20)

        if not query:
            continue

        logger.info("\tGenerated query: %s", query)
        assert lucene_service.match(query, data) == (
            datastore.hit.search(f"({query}) AND howler.id:{hit.howler.id}", rows=0)["total"] > 0
        )
