from types import SimpleNamespace

import elasticsearch
import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from howler.datastore.exceptions import SearchRetryException
from howler.services import lucene_service


def test_response_body_accepts_decoded_mapping_and_elasticsearch_response():
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
    assert len(prepared.split("howler.analytic:", 1)[1].split(" ", 1)[0]) == 64
    assert len(prepared.rsplit(":", 1)[1]) == 64


def test_normalize_lucene_explanation_handles_nested_lucene_10_wrappers():
    lucene_service.SEARCH_PHRASE_CACHE.clear()
    query = 'howler.analytic:"Password Sprayer"'
    prepared = lucene_service.prepare_lucene_query(query)
    phrase_hash = prepared.rsplit(":", 1)[1]

    explanation = (
        "ConstantScoreQuery("
        "BoostQuery("
        f"IndexOrDocValuesQuery(indexQuery=howler.analytic:{phrase_hash}, "
        f"dvQuery=howler.analytic:{phrase_hash}), boost=1.0))"
    )

    assert lucene_service.normalize_lucene_explanation(explanation) == query


def test_normalize_lucene_explanation_supports_old_and_new_exists_shapes():
    assert (
        lucene_service.normalize_lucene_explanation("ConstantScore(FieldExistsQuery [field=howler.id])")
        == "_exists_:howler.id"
    )
    assert (
        lucene_service.normalize_lucene_explanation("ConstantScoreQuery(FieldExistsQuery(field=howler.id))")
        == "_exists_:howler.id"
    )


def test_normalize_lucene_explanation_preserves_nested_range_query():
    explanation = (
        "ConstantScore(IndexOrDocValuesQuery(indexQuery=howler.score:[50 TO 100], dvQuery=howler.score:[50 TO 100]))"
    )

    assert lucene_service.normalize_lucene_explanation(explanation) == "howler.score:[50 TO 100]"


def test_match_accepts_elasticsearch_9_response_wrapper(monkeypatch):
    class Cache:
        def get(self, key):
            return None

        def set(self, key, value):
            self.value = value

    fake_client = SimpleNamespace(
        indices=SimpleNamespace(
            validate_query=lambda **kwargs: ObjectApiResponse(
                {"valid": True, "explanations": [{"explanation": "howler.status:open"}]},
                ApiResponseMeta(status=200, http_version="1.1", headers={}, duration=0.0, node=None),
            )
        )
    )
    fake_datastore = SimpleNamespace(
        hit=SimpleNamespace(datastore=SimpleNamespace(client=fake_client), index_name="howler-hit")
    )
    monkeypatch.setattr(lucene_service, "datastore", lambda: fake_datastore)
    monkeypatch.setattr(lucene_service, "NORMALIZED_QUERY_CACHE", Cache())

    assert lucene_service.match("howler.status:open", {"howler.status": "open"}) is True


def test_match_returns_false_for_validation_errors(monkeypatch):
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
