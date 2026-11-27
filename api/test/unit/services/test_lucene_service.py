from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import MagicMock

import elasticsearch
import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from howler.datastore.exceptions import SearchRetryException
from howler.models.hit import Hit
from howler.services import lucene_service


@pytest.mark.parametrize(
    "query,protected,wildcards",
    [
        (
            r'field:("a \"quoted\" term?" OR (+two\ words\(v1\)* -label\:part?)) AND *:* AND name:literal\*\?',
            {r'"a \"quoted\" term?"', r"two\ words\(v1\)*", r"label\:part?", r"literal\*\?"},
            True,
        ),
        ("name:two\\\twords? OR name:one*\\\\ AND status:open", {"two\\\twords?", "one*\\\\"}, True),
        (
            r'field:(two\ words* OR "two words") AND ip:"2001:db8::1" AND date:"2025-03-27T11:52:37.477958Z"',
            {'"two words"'},
            False,
        ),
    ],
)
def test_prepare_lucene_roundtrips_protected_terms(query, protected, wildcards):
    tokens = {}
    prepared = lucene_service.prepare_lucene_query(query, protect_wildcards=wildcards, tokens=tokens)
    assert set(tokens.values()) == protected
    keys = {value: key for key, value in tokens.items()}
    if query.startswith("field:(") and wildcards:
        phrase, wildcard, bare, literal = (
            keys[value] for value in (r'"a \"quoted\" term?"', r"two\ words\(v1\)*", r"label\:part?", r"literal\*\?")
        )
        assert prepared == f'field:("{phrase}" OR (+{wildcard} -{bare})) AND *:* AND name:{literal}'
    if not wildcards:
        phrase_hash = keys['"two words"']
        assert prepared == query.replace('"two words"', f'"{phrase_hash}"').replace(
            "2001:db8::1", "2001@colondb8@colon@colon1"
        )
    assert lucene_service.normalize_lucene_explanation(prepared, tokens) == query


@pytest.mark.parametrize(
    "bounds", ["[80 TO *]", "[* TO 100]", "{80 TO *}", "[* TO *}", '["a] b" TO *}', r'{a\}b TO "z*"]']
)
def test_prepare_lucene_preserves_ranges(bounds):
    prepared = lucene_service.prepare_lucene_query(f"howler.score:{bounds} AND howler.analytic:malware*")
    assert prepared.startswith(f"howler.score:{bounds} AND howler.analytic:") and "malware*" not in prepared


@pytest.mark.parametrize("wrapper", ["FieldExistsQuery", "DocValuesFieldExistsQuery"])
@pytest.mark.parametrize("shape", ["ConstantScore({} [field=howler.id])", "ConstantScoreQuery({}(field=howler.id))"])
def test_normalize_exists_queries(wrapper, shape):
    assert lucene_service.normalize_lucene_explanation(shape.format(wrapper)) == "_exists_:howler.id"


@pytest.mark.parametrize(
    "explanation,expected",
    [
        ("OtherDocValuesFieldExistsQuery [field=howler.id]", "OtherDocValuesFieldExistsQuery [field=howler.id]"),
        ("OtherFieldExistsQuery(field=howler.id)", "OtherFieldExistsQuery(field=howler.id)"),
        ("MyBoostQuery(foo)", "MyBoostQuery(foo)"),
        (
            "ConstantScore(IndexOrDocValuesQuery(indexQuery=howler.score:[50 TO 100], "
            "dvQuery=howler.score:[50 TO 100]))",
            "howler.score:[50 TO 100]",
        ),
    ],
)
def test_normalize_query_wrappers(explanation, expected):
    assert lucene_service.normalize_lucene_explanation(explanation) == expected


def test_normalize_nested_wrappers_uses_only_request_tokens():
    query = 'howler.analytic:"Password Sprayer"'
    tokens = {}
    lucene_service.prepare_lucene_query(query, tokens=tokens)
    phrase_hash = next(iter(tokens))
    explanation = (
        f"ConstantScoreQuery(BoostQuery(IndexOrDocValuesQuery(indexQuery=howler.analytic:{phrase_hash}, "
        f"dvQuery=howler.analytic:{phrase_hash}), boost=1.0))"
    )
    assert lucene_service.normalize_lucene_explanation(explanation, tokens) == query
    assert lucene_service.normalize_lucene_explanation(explanation) == f"howler.analytic:{phrase_hash}"


@pytest.fixture
def explanations(monkeypatch):
    responses, cache = {}, {}
    validate_query = MagicMock(side_effect=lambda **kwargs: responses[kwargs["q"]])
    client = SimpleNamespace(indices=SimpleNamespace(validate_query=validate_query))
    hit = SimpleNamespace(index_name="hit", datastore=SimpleNamespace(client=client))
    monkeypatch.setattr(
        lucene_service,
        "datastore",
        lambda: SimpleNamespace(hit=hit, ds=SimpleNamespace(get_models=lambda: {"hit": Hit})),
    )
    monkeypatch.setattr(lucene_service, "NORMALIZED_QUERY_CACHE", SimpleNamespace(get=cache.get, set=cache.__setitem__))
    monkeypatch.setattr(lucene_service, "TESTING", False)
    return responses, validate_query


def response(explanation):
    return {"valid": True, "explanations": [{"explanation": explanation}]}


@pytest.mark.parametrize(
    "field,term,matches,misses",
    [
        ("process.name", r"label\*", ["label*"], ["LABEL*", "labelXYZ"]),
        ("process.name", r"label\?", ["label?"], ["LABEL?", "labelX"]),
        ("process.name", r"label\?*", ["label?xyz"], ["LABEL?xyz", "labelXxyz"]),
        ("howler.analytic", r"LaBel\*", ["label*", "LABEL*"], ["labelXYZ"]),
        ("howler.analytic", r"LaBel\?", ["label?", "LABEL?"], ["labelX"]),
        ("howler.analytic", r"İΟΣ\*", ["iοσ*"], ["iος*", "iοσX"]),
    ],
)
def test_match_preserves_escaped_wildcards(explanations, field, term, matches, misses):
    explanations, _ = explanations
    query = f"{field}:{term}"
    prepared = f"{field}:{sha256(term.encode()).hexdigest()}"
    explanations[prepared] = response(prepared)
    assert lucene_service.match(query, {field: matches[0]})
    explanations.clear()
    for candidate in matches:
        assert lucene_service.match(query, {field: candidate})
    for candidate in misses:
        assert not lucene_service.match(query, {field: candidate})


AUTOMATON = "process.name:AutomatonQuery {\norg.apache.lucene.util.automaton.Automaton@4469500b}"
ONE, TWO = (sha256(phrase.encode()).hexdigest() for phrase in ('"one"', '"two"'))


@pytest.mark.parametrize(
    "query,rendering,matches,misses",
    [
        (f"process.name:{regex} OR process.name:ok", f"{AUTOMATON} process.name:ok", ["ok"], ["other"])
        for regex in (r"/foo.*[0-9]/", r"/foo\/bar[0-9]/", r"/foo[() ?*]/")
    ]
    + [
        ("process.name:/foo.*[0-9]/ AND process.name:ok", f"+{AUTOMATON} +process.name:ok", [], ["ok"]),
        ("process.name:foo1 AND NOT process.name:/foo.*[0-9]/", f"+process.name:foo1 -{AUTOMATON}", [], ["foo1"]),
        (
            'process.name:"one"OR process.name:"two"',
            f"process.name:{ONE} process.name:{TWO}",
            ["one", "two"],
            ["three"],
        ),
    ],
)
def test_match_regex_and_phrase_boundaries(explanations, query, rendering, matches, misses):
    explanations, _ = explanations
    if "/foo" in query:
        assert lucene_service.prepare_lucene_query(query, protect_wildcards=False) == query
    prepared = lucene_service.prepare_lucene_query(query)
    explanations[prepared] = response(rendering)
    for name in matches:
        assert lucene_service.match(query, {"process": {"name": name}})
    for name in misses:
        assert not lucene_service.match(query, {"process": {"name": name}})


def test_match_validation_responses(explanations):
    explanations, validate_query = explanations
    query = "howler.status:op?n"
    prepared = f"howler.status:{sha256('op?n'.encode()).hexdigest()}"
    meta = ApiResponseMeta(status=200, http_version="1.1", headers={}, duration=0.0, node=None)
    body = {"valid": True, "explanations": [{"explanation": prepared}]}
    assert lucene_service.response_body(body) == lucene_service.response_body(SimpleNamespace(body=body)) == body
    explanations[prepared] = ObjectApiResponse(body, meta)
    assert lucene_service.match(query, {"howler.status": "open"})
    explanations["status:bad"] = {"valid": False, "error": {"type": "query_shard_exception", "reason": "invalid query"}}
    assert not lucene_service.match("status:bad", {})
    validate_query.side_effect = elasticsearch.ConnectionTimeout("validation timed out")
    with pytest.raises(SearchRetryException):
        lucene_service.match("status:timeout", {})


def test_missing_datastore_model_uses_default(monkeypatch):
    monkeypatch.setattr(lucene_service, "datastore", lambda: SimpleNamespace())
    assert lucene_service._get_hit_model() is Hit
