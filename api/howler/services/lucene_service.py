import fnmatch
import os
import re
import sys
from datetime import datetime, timedelta
from hashlib import sha256
from ipaddress import ip_address
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
from howler.remote.datatypes.hash import Hash
from howler.utils.dict_utils import flatten_deep
from howler.utils.lucene import coerce, normalize_phrase, try_parse_date, try_parse_ip

logger = get_logger(__file__)

TRANSPORT_TIMEOUT = int(os.environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT", "10"))


class LuceneProcessor(TreeVisitor):
    "Tree visitor that evaluates a query on a given object"

    def visit(self, tree: Any, context: dict[str, Any]) -> bool:
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
                # If we run across a MUST or MUST NOT (plus, probhit) object and the value doesn't match, we immediately
                # shortcircuit and return false.
                if isinstance(child, Plus) and not result:
                    yield False
                    return
                elif isinstance(child, Prohibit) and result:
                    yield False
                    return

                # Otherwise, we use a basic OR operation to return a result.
                results.append(result)

        yield any(results)

    @staticmethod
    def __parse_range(low: str, value: Union[list[str], str], high: str) -> Any:
        "Generate the low, value and high components of a range check, ensuring correct types"
        if datetime_result := coerce(value, try_parse_date):
            low_datetime_result = cast(Any, datetime.fromtimestamp(int(low) / 1000, tz=datetime_result.tzinfo))

            high_datetime_result = datetime.fromtimestamp(int(high) / 1000, tz=datetime_result.tzinfo)
            high_datetime_result += timedelta(milliseconds=1)

            return low_datetime_result, datetime_result, high_datetime_result

        try:
            # Check if the value is a simple integer
            return int(low), coerce(value, int), int(high)
        except ValueError:
            pass

        if ip_result := coerce(value, try_parse_ip):
            low_ip_result = ip_address(low)
            high_ip_result = ip_address(high)

            return low_ip_result, ip_result, high_ip_result

        try:
            # Check if the value is a float
            return float(low), coerce(value, float), float(high)
        except ValueError:
            pass

        raise InvalidDataException(f"Unknown range type for values {low} - {value} - {high}")

    def visit_range(self, node: Range, context: dict[str, Any]):
        "Handle range queries"
        low, value, high = self.__parse_range(node.high.value, context["hit"].get(context["field"]), node.low.value)

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
    def __sanitize_value(value: str) -> str:
        "Sanitize the value we are validating against"
        # True/False are shorthanded by elastic - convert back to True/False
        sanitized_value = re.sub(r"^F$", r"False", value)
        sanitized_value = re.sub(r"^T$", r"True", sanitized_value)

        # For phrases, remove the encapsulating quotations
        sanitized_value = re.sub(r'"(.+)"', r"\1", sanitized_value)

        # Unescape escaped colons in value
        sanitized_value = sanitized_value.replace("\\:", ":")

        return sanitized_value

    @staticmethod
    def __build_candidates(value: Union[list[str], str], type: Union[Literal["phrase"], Literal["word"]]) -> list[str]:
        candidates: list[str] = []
        if isinstance(value, list):
            for entry in value:
                candidates += normalize_phrase(str(entry), type)
        else:
            candidates = normalize_phrase(str(value), type)

        return candidates

    def __handle_word_or_phrase(self, node: Union[Phrase, Word], context: dict[str, Any]):
        sanitized_value = self.__sanitize_value(node.value)

        if "field" not in context:
            yield any(value == sanitized_value for value in context["hit"].values())
        elif context["field"] == "_exists_":
            yield context["hit"].get(node.value) is not None
        else:
            candidates = self.__build_candidates(context["hit"].get(context["field"]), context["term_type"])

            yield len(fnmatch.filter(candidates, sanitized_value)) > 0

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
    if (normalized_query := NORMALIZED_QUERY_CACHE.get(hash_key)) is not None or True:
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
