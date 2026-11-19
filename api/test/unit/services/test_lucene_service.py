from hashlib import sha256
from types import SimpleNamespace

import elasticsearch
import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from howler.datastore.exceptions import SearchRetryException
from howler.models.hit import Hit
from howler.services import lucene_service


def test_response_body_accepts_mappings_and_elasticsearch_responses():
    body = {"valid": True, "explanations": []}
    meta = ApiResponseMeta(status=200, http_version="1.1", headers={}, duration=0.0, node=None)

    assert lucene_service.response_body(body) == body
    assert lucene_service.response_body(SimpleNamespace(body=body)) == body
    assert lucene_service.response_body(ObjectApiResponse(body, meta)) == body


def test_prepare_lucene_query_protects_phrases_and_wildcards():
    query = r'howler.analytic:"Password Sprayer" OR process.command_line:*\ -E\ *'

    prepared = lucene_service.prepare_lucene_query(query)

    assert "Password Sprayer" not in prepared
    assert r"*\ -E\ *" not in prepared
    assert len(prepared.split('"')[1]) == 64
    assert len(prepared.rsplit(":", 1)[1]) == 64


def test_prepare_lucene_query_preserves_syntax_around_protected_terms():
    phrase = r'"a \"quoted\" term?"'
    wildcard = r"two\ words\(v1\)*"
    bare = r"label\:part?"
    literal = r"literal\*\?"
    query = f"field:({phrase} OR (+{wildcard} -{bare})) AND *:* AND name:{literal}"
    tokens = {}

    prepared = lucene_service.prepare_lucene_query(query, tokens=tokens)

    keys = {value: key for key, value in tokens.items()}
    assert keys.keys() == {phrase, wildcard, bare, literal}
    assert prepared == f'field:("{keys[phrase]}" OR (+{keys[wildcard]} -{keys[bare]})) AND *:* AND name:{keys[literal]}'
    assert lucene_service.normalize_lucene_explanation(prepared, tokens) == query


def test_prepare_lucene_query_distinguishes_escaped_whitespace_from_escaped_backslash():
    query = "name:two\\\twords? OR name:one*\\\\ AND status:open"
    tokens = {}

    prepared = lucene_service.prepare_lucene_query(query, tokens=tokens)

    assert set(tokens.values()) == {"two\\\twords?", "one*\\\\"}
    assert lucene_service.normalize_lucene_explanation(prepared, tokens) == query


def test_prepare_lucene_query_for_explain_preserves_wildcards_and_typed_phrases():
    query = r'field:(two\ words* OR "two words") AND ip:"2001:db8::1" AND date:"2025-03-27T11:52:37.477958Z"'
    tokens = {}

    prepared = lucene_service.prepare_lucene_query(query, protect_wildcards=False, tokens=tokens)

    assert list(tokens.values()) == ['"two words"']
    assert prepared == query.replace('"two words"', f'"{next(iter(tokens))}"').replace(
        "2001:db8::1", "2001@colondb8@colon@colon1"
    )
    assert lucene_service.normalize_lucene_explanation(prepared, tokens) == query


@pytest.mark.parametrize(
    "bounds", ["[80 TO *]", "[* TO 100]", "{80 TO *}", "[* TO *}", '["a] b" TO *}', r'{a\}b TO "z*"]']
)
def test_prepare_lucene_query_preserves_unbounded_ranges(bounds):
    query = f"howler.score:{bounds} AND howler.analytic:malware*"
    prepared = lucene_service.prepare_lucene_query(query)
    assert prepared.startswith(f"howler.score:{bounds} AND howler.analytic:")
    assert "malware*" not in prepared


def test_normalize_lucene_explanation_handles_nested_query_wrappers():
    query = 'howler.analytic:"Password Sprayer"'
    tokens = {}
    lucene_service.prepare_lucene_query(query, tokens=tokens)
    phrase_hash = next(iter(tokens))

    explanation = (
        "ConstantScoreQuery("
        "BoostQuery("
        f"IndexOrDocValuesQuery(indexQuery=howler.analytic:{phrase_hash}, "
        f"dvQuery=howler.analytic:{phrase_hash}), boost=1.0))"
    )

    assert lucene_service.normalize_lucene_explanation(explanation, tokens) == query
    # An explanation from another request may contain the same hash as a literal term.
    assert lucene_service.normalize_lucene_explanation(explanation) == f"howler.analytic:{phrase_hash}"


@pytest.mark.parametrize("wrapper", ["FieldExistsQuery", "DocValuesFieldExistsQuery"])
@pytest.mark.parametrize("shape", ["ConstantScore({} [field=howler.id])", "ConstantScoreQuery({}(field=howler.id))"])
def test_normalize_lucene_explanation_handles_exists_query_shapes(wrapper, shape):
    assert lucene_service.normalize_lucene_explanation(shape.format(wrapper)) == "_exists_:howler.id"


@pytest.mark.parametrize(
    "explanation",
    ["OtherDocValuesFieldExistsQuery [field=howler.id]", "OtherFieldExistsQuery(field=howler.id)", "MyBoostQuery(foo)"],
)
def test_normalize_lucene_explanation_preserves_unknown_wrapper_names(explanation):
    assert lucene_service.normalize_lucene_explanation(explanation) == explanation


def test_normalize_lucene_explanation_preserves_nested_range_queries():
    explanation = (
        "ConstantScore(IndexOrDocValuesQuery(indexQuery=howler.score:[50 TO 100], dvQuery=howler.score:[50 TO 100]))"
    )

    assert lucene_service.normalize_lucene_explanation(explanation) == "howler.score:[50 TO 100]"


def test_match_accepts_elasticsearch_response_wrappers(monkeypatch):
    class Cache:
        def get(self, key):
            return None

        def set(self, key, value):
            self.value = value

    fake_client = SimpleNamespace(
        indices=SimpleNamespace(
            validate_query=lambda **kwargs: ObjectApiResponse(
                {"valid": True, "explanations": [{"explanation": kwargs["q"]}]},
                ApiResponseMeta(status=200, http_version="1.1", headers={}, duration=0.0, node=None),
            )
        )
    )
    fake_datastore = SimpleNamespace(
        hit=SimpleNamespace(datastore=SimpleNamespace(client=fake_client), index_name="howler-hit")
    )
    monkeypatch.setattr(lucene_service, "datastore", lambda: fake_datastore)
    cache = Cache()
    monkeypatch.setattr(lucene_service, "NORMALIZED_QUERY_CACHE", cache)

    assert lucene_service.match("howler.status:op?n", {"howler.status": "open"}) is True
    assert cache.value == "howler.status:op?n"


@pytest.fixture
def explanations(monkeypatch):
    """Replay the isolated Hit index's validate_query renderings for the prepared queries."""
    responses = {}

    def validate_query(*, q, index, explain):
        return {"valid": True, "explanations": [{"explanation": responses[q]}]}

    client = SimpleNamespace(indices=SimpleNamespace(validate_query=validate_query))
    hit = SimpleNamespace(index_name="hit", datastore=SimpleNamespace(client=client))
    store = SimpleNamespace(get_models=lambda: {"hit": Hit})
    monkeypatch.setattr(lucene_service, "datastore", lambda: SimpleNamespace(hit=hit, ds=store))
    cache = {}
    monkeypatch.setattr(lucene_service, "NORMALIZED_QUERY_CACHE", SimpleNamespace(get=cache.get, set=cache.__setitem__))
    monkeypatch.setattr(lucene_service, "TESTING", False)
    return responses


@pytest.mark.parametrize(
    ("field", "term", "matches", "misses"),
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
    query = f"{field}:{term}"
    prepared = f"{field}:{sha256(term.encode()).hexdigest()}"
    explanations[prepared] = prepared

    assert lucene_service.match(query, {field: matches[0]})
    explanations.clear()  # Subsequent hits must use the cached explanation.
    for candidate in matches:
        assert lucene_service.match(query, {field: candidate})
    for candidate in misses:
        assert not lucene_service.match(query, {field: candidate})


@pytest.mark.parametrize("regex", [r"/foo.*[0-9]/", r"/foo\/bar[0-9]/", r"/foo[() ?*]/"])
def test_match_preserves_regex_as_one_clause(explanations, regex):
    query = f"process.name:{regex} OR process.name:ok"
    explanations[query] = (
        "process.name:AutomatonQuery {\norg.apache.lucene.util.automaton.Automaton@26998730} process.name:ok"
    )

    assert lucene_service.prepare_lucene_query(query, protect_wildcards=False) == query
    assert lucene_service.match(query, {"process": {"name": "ok"}})
    assert not lucene_service.match(query, {"process": {"name": "other"}})


def test_match_does_not_skip_required_or_prohibited_opaque_regex(explanations):
    regex = "process.name:/foo.*[0-9]/"
    automaton = "process.name:AutomatonQuery {\norg.apache.lucene.util.automaton.Automaton@4469500b}"
    required = f"{regex} AND process.name:ok"
    prohibited = f"process.name:foo1 AND NOT {regex}"
    explanations[required] = f"+{automaton} +process.name:ok"
    explanations[prohibited] = f"+process.name:foo1 -{automaton}"

    assert not lucene_service.match(required, {"process": {"name": "ok"}})
    assert not lucene_service.match(prohibited, {"process": {"name": "foo1"}})


def test_match_keeps_phrase_boundaries_next_to_boolean_operators(explanations):
    one, two = (sha256(phrase.encode()).hexdigest() for phrase in ('"one"', '"two"'))
    query = 'process.name:"one"OR process.name:"two"'
    explanations[f'process.name:"{one}"OR process.name:"{two}"'] = f"process.name:{one} process.name:{two}"

    for name in ("one", "two"):
        assert lucene_service.match(query, {"process": {"name": name}})
    assert not lucene_service.match(query, {"process": {"name": "three"}})


def test_match_returns_false_for_query_validation_errors(monkeypatch):
    fake_client = SimpleNamespace(
        indices=SimpleNamespace(
            validate_query=lambda **kwargs: {
                "valid": False,
                "error": {"type": "query_shard_exception", "reason": "invalid query"},
            }
        )
    )
    fake_datastore = SimpleNamespace(
        hit=SimpleNamespace(datastore=SimpleNamespace(client=fake_client), index_name="howler-hit")
    )
    monkeypatch.setattr(lucene_service, "datastore", lambda: fake_datastore)
    monkeypatch.setattr(lucene_service, "NORMALIZED_QUERY_CACHE", SimpleNamespace(get=lambda key: None))

    assert lucene_service.match("howler.status:open", {"howler.status": "open"}) is False


def test_match_propagates_operational_validation_failures(monkeypatch):
    failure = elasticsearch.ConnectionTimeout("validation timed out")
    fake_client = SimpleNamespace(
        indices=SimpleNamespace(validate_query=lambda **kwargs: (_ for _ in ()).throw(failure))
    )
    fake_datastore = SimpleNamespace(
        hit=SimpleNamespace(datastore=SimpleNamespace(client=fake_client), index_name="howler-hit")
    )
    monkeypatch.setattr(lucene_service, "datastore", lambda: fake_datastore)
    monkeypatch.setattr(lucene_service, "NORMALIZED_QUERY_CACHE", SimpleNamespace(get=lambda key: None))

    with pytest.raises(SearchRetryException):
        lucene_service.match("howler.status:open", {"howler.status": "open"})
