import json
from pathlib import Path
from typing import cast

import pytest

from howler.common import loader
from howler.common.logging import get_logger
from howler.datastore.howler_store import HowlerDatastore
from howler.odm import Model
from howler.odm.helper import generate_useful_hit
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj
from howler.services import lucene_service
from test.utils.queries import generate_lucene_query

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


def test_lucene_wildcard_with_spaces(datastore: HowlerDatastore):
    """Regression test for wildcard queries with escaped spaces not matching in lucene_service.

    Dossier queries such as:
        (process.command_line:*\\ -E\\ * OR process.command_line:*\\ -Enc\\ * OR
         process.command_line:*\\ -EncodedCommand\\ *) AND process.name:powershell.exe

    would fail to match hits in lucene_service.match() even though the same query returns
    results from Elasticsearch. The test validates that both agree on the result.
    """
    powershell_hit: Hit = random_model_obj(cast(Model, Hit))
    powershell_hit.process.name = "powershell.exe"
    powershell_hit.process.command_line = "powershell.exe -EncodedCommand dGVzdA=="

    datastore.hit.save(powershell_hit.howler.id, powershell_hit)
    datastore.hit.commit()

    data = powershell_hit.as_primitives()

    queries = [
        r"process.name:powershell.exe",
        (
            r"(process.command_line:*\ -E\ * OR process.command_line:*\ -Enc\ *"
            r" OR process.command_line:*\ -EncodedCommand\ *) AND process.name:powershell.exe"
        ),
        r"process.command_line:(*\ -E\ * OR *\ -Enc\ * OR *\ -EncodedCommand\ *) AND process.name:powershell.exe",
    ]

    for query in queries:
        es_result = datastore.hit.search(f"({query}) AND howler.id:{powershell_hit.howler.id}", rows=0)["total"] > 0
        lucene_result = lucene_service.match(query, data)
        assert lucene_result == es_result, (
            f"lucene_service.match returned {lucene_result} but Elasticsearch returned {es_result}"
            f" for query: {query}"
        )
