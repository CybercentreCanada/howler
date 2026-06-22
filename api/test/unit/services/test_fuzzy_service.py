from howler.services.fuzzy_service import (
    _classify_boosted_fields,
    _detect_token_type,
    _escape_query_string,
    _get_ip_typed_fields,
    build_fuzzy_query,
)


class TestDetectTokenType:
    def test_ipv4(self):
        assert _detect_token_type("192.168.1.1") == "ip"
        assert _detect_token_type("10.0.0.1") == "ip"
        assert _detect_token_type("255.255.255.255") == "ip"

    def test_ipv6(self):
        assert _detect_token_type("2001:0db8:85a3:0000:0000:8a2e:0370:7334") == "ip"
        assert _detect_token_type("fe80:0000:0000:0000:0204:61ff:fe9d:f156") == "ip"

    def test_ip_typed_fields_detected(self):
        """Verify dynamic IP field detection finds known IP fields from the ODM models."""
        ip_fields = _get_ip_typed_fields()
        assert "related.ip" in ip_fields
        assert "source.ip" in ip_fields or "destination.ip" in ip_fields

    def test_md5(self):
        assert _detect_token_type("d41d8cd98f00b204e9800998ecf8427e") == "md5"

    def test_sha1(self):
        assert _detect_token_type("da39a3ee5e6b4b0d3255bfef95601890afd80709") == "sha1"

    def test_sha256(self):
        assert _detect_token_type("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") == "sha256"

    def test_email(self):
        assert _detect_token_type("user@example.com") == "email"
        assert _detect_token_type("admin@domain.org") == "email"

    def test_url(self):
        assert _detect_token_type("http://example.com/path") == "url"
        assert _detect_token_type("https://evil.com/malware") == "url"

    def test_domain(self):
        assert _detect_token_type("example.com") == "domain"
        assert _detect_token_type("sub.domain.co.uk") == "domain"

    def test_text(self):
        assert _detect_token_type("hello world") == "text"
        assert _detect_token_type("admin") == "text"
        assert _detect_token_type("suspicious activity") == "text"


class TestBuildFuzzyQuery:
    def test_basic_text_query(self):
        result = build_fuzzy_query("suspicious login", ["hit"])
        assert "query" in result
        assert "bool" in result["query"]
        assert "should" in result["query"]["bool"]
        assert result["query"]["bool"]["minimum_should_match"] == 1

        should = result["query"]["bool"]["should"]
        # Must have at least the fuzzy best_fields clause
        assert len(should) >= 1
        assert should[0]["multi_match"]["type"] == "best_fields"
        assert should[0]["multi_match"]["fuzziness"] == "AUTO"
        # If a phrase_prefix clause exists, it must only target text-type fields
        pp_clauses = [c for c in should if "multi_match" in c and c["multi_match"]["type"] == "phrase_prefix"]
        for clause in pp_clauses:
            pp_fields = clause["multi_match"]["fields"]
            assert not any("howler.id" in f for f in pp_fields)
            assert not any("case_id" in f for f in pp_fields)

    def test_phrase_prefix_excludes_keyword_fields(self):
        """phrase_prefix queries only work on text fields; keyword fields must be excluded."""
        field_classes = _classify_boosted_fields()
        result = build_fuzzy_query("some query", ["hit", "observable", "case"])
        should = result["query"]["bool"]["should"]
        pp_clauses = [c for c in should if "multi_match" in c and c["multi_match"]["type"] == "phrase_prefix"]
        for clause in pp_clauses:
            for field_str in clause["multi_match"]["fields"]:
                field_name = field_str.rsplit("^", 1)[0]
                assert field_classes.get(field_name) == "text", (
                    f"{field_name} is {field_classes.get(field_name)}, not text — phrase_prefix would fail"
                )

    def test_short_text_no_phrase_prefix(self):
        result = build_fuzzy_query("ab", ["hit"])
        should = result["query"]["bool"]["should"]
        # Should not have phrase_prefix for short text
        pp = [c for c in should if "multi_match" in c and c["multi_match"]["type"] == "phrase_prefix"]
        assert len(pp) == 0
        mm = [c for c in should if "multi_match" in c]
        assert len(mm) >= 1
        assert mm[0]["multi_match"]["type"] == "best_fields"

    def test_ip_query_uses_term_for_ip_fields(self):
        result = build_fuzzy_query("192.168.1.1", ["hit", "observable"])
        should = result["query"]["bool"]["should"]
        # Should have term queries for IP fields + one multi_match for text fields
        term_clauses = [c for c in should if "term" in c]
        multi_clauses = [c for c in should if "multi_match" in c]
        assert len(term_clauses) >= 1
        assert len(multi_clauses) == 1
        assert multi_clauses[0]["multi_match"]["type"] == "best_fields"
        # IP fields should not appear in the multi_match fields list
        mm_fields = multi_clauses[0]["multi_match"]["fields"]
        assert not any("source.ip" in f for f in mm_fields)
        assert not any("destination.ip" in f for f in mm_fields)
        assert not any("related.ip" in f for f in mm_fields)

    def test_hash_query_uses_best_fields(self):
        result = build_fuzzy_query("d41d8cd98f00b204e9800998ecf8427e", ["hit"])
        should = result["query"]["bool"]["should"]
        mm = [c for c in should if "multi_match" in c]
        assert len(mm) == 1
        assert mm[0]["multi_match"]["type"] == "best_fields"

    def test_email_query_uses_phrase(self):
        result = build_fuzzy_query("user@example.com", ["hit", "observable"])
        should = result["query"]["bool"]["should"]
        mm = [c for c in should if "multi_match" in c]
        assert len(mm) == 2
        assert mm[0]["multi_match"]["type"] == "phrase"
        assert mm[1]["multi_match"]["type"] == "best_fields"

    def test_domain_query_uses_phrase(self):
        result = build_fuzzy_query("evil.example.com", ["observable"])
        should = result["query"]["bool"]["should"]
        mm = [c for c in should if "multi_match" in c]
        assert len(mm) == 2
        assert mm[0]["multi_match"]["type"] == "phrase"

    def test_filters_applied(self):
        result = build_fuzzy_query("test", ["hit"], filters=["howler.status:open"])
        assert "filter" in result["query"]["bool"]
        filter_clauses = result["query"]["bool"]["filter"]
        assert len(filter_clauses) == 1
        assert filter_clauses[0]["query_string"]["query"] == "howler.status:open"

    def test_access_control_applied(self):
        result = build_fuzzy_query("test", ["hit"], access_control="access_control:TLP:W")
        filter_clauses = result["query"]["bool"]["filter"]
        assert any(f["query_string"]["query"] == "access_control:TLP:W" for f in filter_clauses)

    def test_multiple_filters_and_access_control(self):
        result = build_fuzzy_query(
            "test",
            ["hit"],
            filters=["howler.status:open", "howler.escalation:alert"],
            access_control="access_control:TLP:W",
        )
        filter_clauses = result["query"]["bool"]["filter"]
        assert len(filter_clauses) == 3

    def test_no_filter_key_when_empty(self):
        result = build_fuzzy_query("test", ["hit"], filters=None, access_control=None)
        assert "filter" not in result["query"]["bool"]

    def test_multiple_indexes_combines_fields(self):
        result = build_fuzzy_query("test", ["hit", "observable", "case"])
        should = result["query"]["bool"]["should"]
        fields = should[0]["multi_match"]["fields"]
        # Should contain text/keyword fields from all three indexes
        assert any("howler.id" in f for f in fields)
        assert any("case_id" in f for f in fields)
        # IP fields should NOT be in multi_match for text queries
        assert not any("source.ip" in f for f in fields)
        assert not any("destination.ip" in f for f in fields)

    def test_whitespace_trimmed(self):
        result = build_fuzzy_query("  192.168.1.1  ", ["hit"])
        should = result["query"]["bool"]["should"]
        # First clause for IP is a term query
        term_clauses = [c for c in should if "term" in c]
        assert len(term_clauses) >= 1
        # Check the term value is trimmed
        term_field = list(term_clauses[0]["term"].keys())[0]
        assert term_clauses[0]["term"][term_field]["value"] == "192.168.1.1"

    def test_field_boosts_present(self):
        result = build_fuzzy_query("test", ["hit"])
        should = result["query"]["bool"]["should"]
        fields = should[0]["multi_match"]["fields"]
        # Check that fields have boost values
        assert any("^" in f for f in fields)
        assert "howler.id^5" in fields

    def test_all_queries_include_catch_all(self):
        """Every query type should include a query_string catch-all clause."""
        for q in ["192.168.1.1", "d41d8cd98f00b204e9800998ecf8427e", "user@example.com", "test query"]:
            result = build_fuzzy_query(q, ["hit"])
            should = result["query"]["bool"]["should"]
            qs_clauses = [c for c in should if "query_string" in c]
            assert len(qs_clauses) == 1, f"Expected 1 query_string clause for q={q!r}, got {len(qs_clauses)}"
            assert qs_clauses[0]["query_string"]["default_field"] == "*"
            assert qs_clauses[0]["query_string"]["boost"] == 0.5

    def test_catch_all_escapes_special_chars(self):
        """Special Lucene characters in the query must be escaped in the catch-all."""
        assert _escape_query_string("foo:bar") == "foo\\:bar"
        assert _escape_query_string("a+b") == "a\\+b"
        assert _escape_query_string('test"val') == 'test\\"val'
        # Plain text should pass through unchanged
        assert _escape_query_string("hello world") == "hello world"
