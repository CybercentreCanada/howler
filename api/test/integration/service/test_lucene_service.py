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


def test_lucene_and_not(datastore: HowlerDatastore):
    """Regression test for AND NOT / minus-prefix negation not working in lucene_service.

    Dossier queries such as:

        _exists_:threat.technique.id AND NOT howler.labels.assignments:example_label

    showed on alerts that DID have the 'example_label' assignment label (Case 1 in report).

        _exists_:agent.id AND _exists_:organization.name AND NOT howler.labels.assignments:example_label

    did not show on alerts that lacked 'example_label' but should have matched (Case 2 in report).

        _exists_:organization.name -howler.analytic:SOME_ANALYTIC
            -organization.name:"GOC" -howler.labels.assignments:example_label

    was not showing on valid alerts (Case 3 in report — minus-prefix negation syntax).

    The test creates two hits — one with the 'example_label' assignment label and one without — and
    validates that lucene_service.match() and Elasticsearch agree on the result for each query.
    """
    # Hit WITH "example_label" label — should be *excluded* by `NOT howler.labels.assignments:example_label`
    example_hit: Hit = random_model_obj(cast(Model, Hit))
    example_hit.howler.labels.assignments = ["example_label"]
    example_hit.howler.analytic = "TEST_ANALYTIC"
    example_hit.threat.technique.id = "T1001"
    example_hit.agent.id = "agent-example_label-001"
    example_hit.organization.name = "Example Corp"

    # Hit WITHOUT "example_label" label — should be *included* by `NOT howler.labels.assignments:example_label`
    clean_hit: Hit = random_model_obj(cast(Model, Hit))
    clean_hit.howler.labels.assignments = []
    clean_hit.howler.analytic = "TEST_ANALYTIC"
    clean_hit.threat.technique.id = "T1001"
    clean_hit.agent.id = "agent-clean-002"
    clean_hit.organization.name = "Example Corp"

    datastore.hit.save(example_hit.howler.id, example_hit)
    datastore.hit.save(clean_hit.howler.id, clean_hit)
    datastore.hit.commit()

    queries = [
        # Case 1: AND NOT with a single required _exists_ field
        "_exists_:threat.technique.id AND NOT howler.labels.assignments:example_label",
        # Case 2: AND NOT with multiple required _exists_ fields
        "_exists_:agent.id AND _exists_:organization.name AND NOT howler.labels.assignments:example_label",
        # Case 3: minus-prefix (dash) negation syntax
        (
            "_exists_:organization.name -howler.analytic:SOME_ANALYTIC"
            ' -organization.name:"GOC" -howler.labels.assignments:example_label'
        ),
    ]

    for test_hit in [example_hit, clean_hit]:
        data = test_hit.as_primitives()
        for query in queries:
            es_result = datastore.hit.search(f"({query}) AND howler.id:{test_hit.howler.id}", rows=0)["total"] > 0
            lucene_result = lucene_service.match(query, data)
            assert lucene_result == es_result, (
                f"lucene_service.match returned {lucene_result} but Elasticsearch returned {es_result}"
                f" for query: {query}"
                f" (hit labels.assignments={test_hit.howler.labels.assignments})"
            )
