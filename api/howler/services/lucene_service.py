import fnmatch
import os
import re
import struct
import sys
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Literal, Union, cast

from elasticsearch._sync.client.indices import IndicesClient
from luqum.parser import parser
from luqum.tree import AndOperation, BoolOperation, Phrase, Plus, Prohibit, Range, SearchField, Word
from luqum.utils import UnknownOperationResolver
from luqum.visitor import TreeVisitor

from howler.api import get_logger
from howler.common.exceptions import InvalidDataException
from howler.common.loader import datastore
from howler.config import redis
from howler.datastore.constants import NORMALIZER_MAPPING
from howler.odm import Boolean, Float, Model, Text
from howler.odm.models.hit import Hit
from howler.remote.datatypes.hash import Hash
from howler.utils.constants import TESTING
from howler.utils.dict_utils import flatten_deep
from howler.utils.lucene import coerce, normalize_phrase, try_parse_date, try_parse_ip, try_parse_number

logger = get_logger(__file__)

TRANSPORT_TIMEOUT = int(os.environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT", "10"))

CASE_INSENSITIVE_FIELD_TYPES = (
    *(field_cls for field_cls, normalizer in NORMALIZER_MAPPING.items() if normalizer == "lowercase_normalizer"),
    Boolean,
    Text,
)
_HIT_FIELDS_CACHE: tuple[tuple[Any, ...], dict[str, Any]] | None = None


def _get_hit_field(field_name: str) -> Any:
    "Resolve an ODM field from the initialized Hit model, refreshing when namespaces change."
    global _HIT_FIELDS_CACHE
    hit_model = m if isinstance(m := datastore().ds.get_models().get("hit"), type) and issubclass(m, Model) else Hit
    cache_key = (hit_model, *hit_model.fields().items())
    if _HIT_FIELDS_CACHE is None or _HIT_FIELDS_CACHE[0] != cache_key:
        _HIT_FIELDS_CACHE = (cache_key, hit_model.flat_fields())
    return _HIT_FIELDS_CACHE[1].get(field_name)


def is_case_insensitive_field(field_name: str) -> bool:
    "Check whether an Elasticsearch Hit field performs case-insensitive matching."
    return field_name == "__text__" or isinstance(_get_hit_field(field_name), CASE_INSENSITIVE_FIELD_TYPES)


class LuceneProcessor(TreeVisitor):
    "Tree visitor that evaluates a query on a given object"

    def visit(self, tree: Any, context: dict[str, Any]) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        "Visit each node in a tree"
        return super().visit(tree, context)[0]

    def visit_search_field(self, node: SearchField, context: dict[str, Any]):
        "Handle search fields"
        # The actual validation happens in the word/phrases directly, not the search field.
        # We pass the field name down for use later
        for result in self.generic_visit(node, {**context, "field": node.name}):
            yield result

    def visit_and_operation(self, node: AndOperation, context: dict[str, Any]):
        "Handle AND results in query"
        yield all(list(self.generic_visit(node, context)))

    def visit_or_operation(self, node: AndOperation, context: dict[str, Any]):
        "Handle OR results in query"
        yield any(list(self.generic_visit(node, context)))

    def visit_bool_operation(self, node: BoolOperation, context: dict[str, Any]):
        """Handle the insanity that is boolean operations.

        For information about how boolean operations work, see the following extremely helpful article:

            https://lucidworks.com/resources/solr-boolean-operators/

        However, we are operating in a boolean environment instead of rankings, so the behaviour is slightly modified.
        """
        results: list[bool] = []
        for child in node.children:
            child_context = self.child_context(node, child, context)
            for result in self.visit_iter(child, context=child_context):
                # If we run across a MUST or MUST NOT (plus, prohibit) object and the value doesn't match, we
                # immediately shortcircuit and return false.
                # NOTE: visit_prohibit already negates the inner result, so a violated MUST NOT arrives here as
                # False (not True). We therefore short-circuit on `not result` rather than `result`.
                if isinstance(child, Plus) and not result:
                    yield False
                    return
                elif isinstance(child, Prohibit) and not result:
                    yield False
                    return

                # Otherwise, we use a basic OR operation to return a result.
                results.append(result)

        yield any(results)

    @staticmethod
    def __to_float32(val: int | float) -> float:
        "Round numbers to 32-bit IEEE 754 float precision to match Elasticsearch 'float' fields."
        return struct.unpack("f", struct.pack("f", float(val)))[0]

    @staticmethod
    def __extract_range_bound(bound: Any) -> str:
        "Extract a string bound from a luqum Range endpoint, preserving negative signs parsed as Prohibit."
        if isinstance(bound, Prohibit):
            return f"-{LuceneProcessor.__extract_range_bound(bound.children[0])}"
        return bound.value

    @staticmethod
    def __parse_range(low: str, value: Any, high: str, *, is_float32: bool = False) -> Any:
        "Generate the low, value and high components of a range check, ensuring correct types"
        datetime_result = coerce(value, try_parse_date)
        if datetime_result is not None and datetime_result != []:
            tz = datetime_result[0].tzinfo if isinstance(datetime_result, list) else datetime_result.tzinfo
            low_datetime_result = cast(Any, datetime.fromtimestamp(int(low) / 1000, tz=tz))

            high_datetime_result = datetime.fromtimestamp(int(high) / 1000, tz=tz)
            high_datetime_result += timedelta(milliseconds=1)

            return low_datetime_result, datetime_result, high_datetime_result

        number_result = coerce(value, try_parse_number)
        if number_result is not None and number_result != []:
            low_number_result = coerce(low, try_parse_number)
            high_number_result = coerce(high, try_parse_number)

            if low_number_result is not None and high_number_result is not None:
                if is_float32:
                    low_number_result = LuceneProcessor.__to_float32(low_number_result)
                    high_number_result = LuceneProcessor.__to_float32(high_number_result)
                    number_result = coerce(number_result, LuceneProcessor.__to_float32)

                return low_number_result, number_result, high_number_result

        try:
            # Check if the value is a simple integer
            return int(low), coerce(value, int), int(high)
        except ValueError:
            pass

        ip_result = coerce(value, try_parse_ip)
        if ip_result is not None and ip_result != []:
            low_ip_result = coerce(low, try_parse_ip)
            high_ip_result = coerce(high, try_parse_ip)

            if low_ip_result is not None and high_ip_result is not None:
                return low_ip_result, ip_result, high_ip_result

        try:
            # Check if the value is a float
            return float(low), coerce(value, float), float(high)
        except ValueError:
            pass

        raise InvalidDataException(f"Unknown range type for values {low} - {value} - {high}")

    def visit_range(self, node: Range, context: dict[str, Any]):
        "Handle range queries"
        if (raw_value := context["hit"].get(context["field"])) is None:
            yield False
            return

        low, value, high = self.__parse_range(
            self.__extract_range_bound(node.low),
            raw_value,
            self.__extract_range_bound(node.high),
            is_float32=isinstance(_get_hit_field(context["field"]), Float),
        )

        if isinstance(value, list):
            values = value
        else:
            values = [value]

        result = False
        for _value in values:
            if low <= _value and _value <= high:
                if not node.include_high and _value == high:
                    continue
                elif not node.include_low and _value == low:
                    continue

                result = True
                break

        yield result

    @staticmethod
    def __sanitize_value(value: str, *, expand_booleans: bool = False) -> str:
        "Sanitize the value we are validating against"
        # True/False are shorthanded by elastic - convert back to True/False for boolean fields
        sanitized_value = re.sub(r"^T$", r"True", re.sub(r"^F$", r"False", value)) if expand_booleans else value

        # For phrases, remove the encapsulating quotations
        sanitized_value = re.sub(r'"(.+)"', r"\1", sanitized_value)

        # Unescape escaped colons in value
        sanitized_value = sanitized_value.replace("\\:", ":")

        # Unescape Lucene-escaped spaces so fnmatch can match them correctly
        # (fnmatch does not treat \ as an escape character, so *\ foo\ * would require
        # a literal backslash in the candidate rather than matching a space)
        sanitized_value = sanitized_value.replace("\\ ", " ")

        return sanitized_value

    @staticmethod
    def __build_candidates(
        value: Any, type: Union[Literal["phrase"], Literal["word"]], *, case_insensitive: bool = False
    ) -> list[str]:
        entries = value if isinstance(value, list) else [value]
        return [c for entry in entries for c in normalize_phrase(str(entry), type, case_insensitive=case_insensitive)]

    def __handle_word_or_phrase(self, node: Union[Phrase, Word], context: dict[str, Any]):
        if "field" not in context:
            sanitized_value = self.__sanitize_value(node.value)
            yield any(value == sanitized_value for value in context["hit"].values())
        elif context["field"] == "_exists_":
            yield context["hit"].get(node.value) is not None
        elif context["field"] == "*" and node.value == "*":
            yield True
        elif (raw_value := context["hit"].get(field_name := context["field"])) is None:
            yield False
        else:
            entries = raw_value if isinstance(raw_value, list) else [raw_value]
            is_bool = isinstance(_get_hit_field(field_name), Boolean) or any(isinstance(e, bool) for e in entries)
            sanitized_value = self.__sanitize_value(node.value, expand_booleans=is_bool)
            if case_insensitive := is_case_insensitive_field(field_name):
                sanitized_value = sanitized_value.lower()
            candidates = self.__build_candidates(raw_value, context["term_type"], case_insensitive=case_insensitive)
            yield any(fnmatch.fnmatchcase(candidate, sanitized_value) for candidate in candidates)

    def visit_word(self, node: Phrase, context: dict[str, Any]):
        "Handle words"
        yield from self.__handle_word_or_phrase(node, {**context, "term_type": "word"})

    def visit_phrase(self, node: Phrase, context: dict[str, Any]):
        "Handle phrases"
        yield from self.__handle_word_or_phrase(node, {**context, "term_type": "phrase"})

    def visit_prohibit(self, node: Prohibit, context: dict[str, Any]):
        "Handle NOT operation"
        yield from (not entry for entry in self.generic_visit(node, context))


NORMALIZED_QUERY_CACHE: Hash[str] = Hash("normalized_queries", redis)

SEARCH_PHRASE_CACHE: dict[str, re.Match[str]] = {}


def replace_lucene_phrase(match: re.Match[str]) -> str:
    "Replace a phrase in lucene with its sha256 hash, to circumvent mangling by ES"
    result = match.group(2) or ""

    value = match.group(3)

    if try_parse_date(value.replace('"', "")):
        result += value
    elif try_parse_ip(value.replace('"', "")):
        result += value.replace(":", "@colon")
    else:
        key = sha256(value.encode()).hexdigest()

        SEARCH_PHRASE_CACHE[key] = match

        result += key

    result += match.group(4) or ""

    return result


def try_reinsert_lucene_phrase(match: re.Match[str]) -> str:
    "Given a potential sha256 hash, replace that hash with the original lucene phrase (if it exists)"
    key = match.group(1)

    if key in SEARCH_PHRASE_CACHE:
        return SEARCH_PHRASE_CACHE[key].group(3)
    else:
        return key


def match(lucene: str, obj: dict[str, Any]):
    "Check if a given lucene query matches the given object"
    hash_key = sha256(lucene.encode()).hexdigest()

    # We cache the results back from ES, since we will frequently run the same validation queries over and over again.
    if (normalized_query := NORMALIZED_QUERY_CACHE.get(hash_key)) is None or TESTING:
        # This regex checks for lucene phrases (i.e. the "Example Analytic" part of howler.analytic:"Example Analytic")
        # And then escapes them.
        # https://regex101.com/r/8u5F6a/1
        escaped_lucene = re.sub(r'((:\()?(".+?")(\)?))', replace_lucene_phrase, lucene)

        # This may seem unintuitive, but elastic parses lucene queries in somewhat nonstandard ways (or at least,
        # in ways luqum doesn't agree with). to circumvent this, we use validate_query, which returns a "normalized"
        # query that works much better with luqum. It's also much faster than actually searching for the hit in
        # question.
        indices_client = IndicesClient(datastore().hit.datastore.client)
        result = indices_client.validate_query(q=escaped_lucene, explain=True, index=datastore().hit.index_name)

        if not result["valid"]:
            logger.error("Invalid lucene query:\n%s", result["explanations"][0]["error"])
            return False

        # As an example, the query:
        #   server.address:("supports" OR "their") AND howler.votes.benign:("edge" OR "also")
        # becomes:
        #   +(server.address:supports server.address:their) +(howler.votes.benign:edge howler.votes.benign:also)
        # which means the two are equivalent in elastic, but the second one is a lot less ambiguous to parse.
        normalized_query = cast(str, result["explanations"][0]["explanation"])

        normalized_query = re.sub(r"IndexOrDocValuesQuery *\(indexQuery=(.+?), dvQuery=.+?\)", r"\1", normalized_query)

        # Elastic's explanation mangles exists queries. Since we will handle them the normal way, reset their changes
        normalized_query = re.sub(r"FieldExistsQuery *\[.*?field=(.+?)]", r"_exists_:\1", normalized_query)
        normalized_query = re.sub(r"ConstantScore", "", normalized_query)
        # try and reinsert any phrases we have replaced with sha256 hashes
        normalized_query = re.sub(r"([0-9a-f]{64})", try_reinsert_lucene_phrase, normalized_query)

        # Properly convert escaped colons back
        normalized_query = normalized_query.replace("@colon", ":")

        # Cache the normalized query
        NORMALIZED_QUERY_CACHE.set(hash_key, normalized_query)

    try:
        # luqum's default tree will return UnknownOperations in cases where expilicit operators aren't used.
        # Due to the normalization step undertaken by elastic, we know that all unknown operations are actually
        # Boolean operations.
        #
        # NOTE: Boolean operations have a special meaning in lucene, and are not analgous to and/or operations.
        # For more information, see: https://lucidworks.com/resources/solr-boolean-operators/
        tree = UnknownOperationResolver(resolve_to=BoolOperation)(parser.parse(normalized_query))

        # Actually run the validation
        return LuceneProcessor(track_parents=True).visit(tree, {"hit": flatten_deep(obj)})
    except Exception:
        logger.exception("Exception on processing lucene:")
        return False


if __name__ == "__main__":
    hit = datastore().hit.search("howler.id:*", rows=1, as_obj=False)["items"][0]

    print(match(sys.argv[1], hit))  # noqa: T201
