import fnmatch
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Literal, Union, cast

import elasticsearch
from luqum.parser import parser
from luqum.tree import AndOperation, BoolOperation, Phrase, Plus, Prohibit, Range, SearchField, Word
from luqum.utils import UnknownOperationResolver
from luqum.visitor import TreeVisitor

from howler.api import get_logger
from howler.common.exceptions import InvalidDataException
from howler.common.loader import datastore
from howler.config import redis
from howler.datastore.exceptions import SearchException, SearchRetryException
from howler.datastore.support.elastic import error_message, response_body
from howler.remote.datatypes.hash import Hash
from howler.utils.constants import TESTING
from howler.utils.dict_utils import flatten_deep
from howler.utils.lucene import coerce, normalize_phrase, try_parse_date, try_parse_ip, try_parse_number

logger = get_logger(__file__)

TRANSPORT_TIMEOUT = int(os.environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT", "10"))


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
    def __parse_range(low: str, value: Union[list[str], str], high: str) -> Any:
        "Generate the low, value and high components of a range check, ensuring correct types"
        if datetime_result := coerce(value, try_parse_date):
            low_datetime_result = cast(Any, datetime.fromtimestamp(int(low) / 1000, tz=datetime_result.tzinfo))

            high_datetime_result = datetime.fromtimestamp(int(high) / 1000, tz=datetime_result.tzinfo)
            high_datetime_result += timedelta(milliseconds=1)

            return low_datetime_result, datetime_result, high_datetime_result

        if number_result := coerce(value, try_parse_number):
            low_number_result = coerce(low, try_parse_number)
            high_number_result = coerce(high, try_parse_number)

            if low_number_result is not None and high_number_result is not None:
                return low_number_result, number_result, high_number_result

        try:
            # Check if the value is a simple integer
            return int(low), coerce(value, int), int(high)
        except ValueError:
            pass

        if ip_result := coerce(value, try_parse_ip):
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
        low, value, high = self.__parse_range(node.low.value, context["hit"].get(context["field"]), node.high.value)

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

        # Unescape Lucene-escaped spaces so fnmatch can match them correctly
        # (fnmatch does not treat \ as an escape character, so *\ foo\ * would require
        # a literal backslash in the candidate rather than matching a space)
        sanitized_value = sanitized_value.replace("\\ ", " ")

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

SEARCH_PHRASE_CACHE: dict[str, str] = {}
WILDCARD_TOKEN_PATTERN = re.compile(r'(?:(?<=\()|(?<!\S))((?:\\.|[^\s()"])*[?*](?:\\.|[^\s()"])*)(?=$|[\s)])')
LUCENE_HASH_PATTERN = re.compile(r"([0-9a-f]{64})")


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

        SEARCH_PHRASE_CACHE[key] = value

        result += key

    result += match.group(4) or ""

    return result


def try_reinsert_lucene_phrase(match: re.Match[str]) -> str:
    "Given a potential sha256 hash, replace that hash with the original lucene phrase (if it exists)"
    key = match.group(1)

    if key in SEARCH_PHRASE_CACHE:
        return SEARCH_PHRASE_CACHE[key]
    else:
        return key


def replace_lucene_wildcard(match: re.Match[str]) -> str:
    """Replace a wildcard value with a stable term before requesting a Lucene explanation."""
    wildcard_expression = match.group(1)
    if wildcard_expression == "*:*":
        return wildcard_expression

    field, separator, value = wildcard_expression.partition(":")
    if not separator:
        value = field
        field = ""

    key = sha256(value.encode()).hexdigest()
    SEARCH_PHRASE_CACHE[key] = value
    return f"{field}{separator}{key}"


def prepare_lucene_query(lucene: str, *, protect_wildcards: bool = True) -> str:
    """Protect Lucene phrases and wildcards while Elasticsearch explains a query."""
    escaped_lucene = re.sub(r'((:\()?(".+?")(\)?))', replace_lucene_phrase, lucene)
    if protect_wildcards:
        return WILDCARD_TOKEN_PATTERN.sub(replace_lucene_wildcard, escaped_lucene)
    return escaped_lucene


def _matching_parenthesis(value: str, opening: int) -> int | None:
    """Find the closing parenthesis for an unescaped opening parenthesis."""
    depth = 0
    quoted = False
    escaped = False

    for position in range(opening, len(value)):
        character = value[position]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if quoted:
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return position

    return None


def _top_level_comma_position(value: str) -> int | None:
    """Find the first comma that is not nested in query syntax."""
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    quoted = False
    escaped = False

    for position, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if quoted:
            continue
        if character in depths:
            depths[character] += 1
        elif character in closing:
            depths[closing[character]] = max(0, depths[closing[character]] - 1)
        elif character == "," and not any(depths.values()):
            return position

    return None


def _first_query_argument(value: str, argument_name: str | None = None) -> str:
    """Extract the first top-level query argument from a Lucene query wrapper."""
    if argument_name:
        argument_match = re.search(rf"(?:^|,\s*){re.escape(argument_name)}\s*=", value)
        if argument_match:
            value = value[argument_match.end() :]

    comma = _top_level_comma_position(value)
    return value[:comma].strip() if comma is not None else value.strip()


def _rewrite_query_wrapper(value: str, wrapper: str, argument_name: str | None = None, prefix: str = "") -> str:
    """Replace wrapped Lucene query text with its parseable inner query."""
    marker = f"{wrapper}("
    position = value.find(marker)

    while position != -1:
        closing = _matching_parenthesis(value, position + len(wrapper))
        if closing is None:
            break

        content = value[position + len(marker) : closing]
        replacement = f"{prefix}{_first_query_argument(content, argument_name)}"
        value = f"{value[:position]}{replacement}{value[closing + 1 :]}"
        position = value.find(marker, position + len(replacement))

    return value


def normalize_lucene_explanation(explanation: str) -> str:
    """Convert Elasticsearch/Lucene explain text to the stable query syntax we parse.

    Lucene 10 changed several implementation details in explain strings and can
    nest ``IndexOrDocValuesQuery`` wrappers more deeply.  Query wrappers are
    removed with balanced-parenthesis parsing instead of regexes so ranges,
    boolean queries, and nested wrappers remain intact.
    """
    normalized = explanation.strip()

    for _ in range(8):
        previous = normalized
        normalized = _rewrite_query_wrapper(normalized, "IndexOrDocValuesQuery", "indexQuery")
        normalized = _rewrite_query_wrapper(normalized, "ConstantScore")
        normalized = _rewrite_query_wrapper(normalized, "ConstantScoreQuery")
        normalized = _rewrite_query_wrapper(normalized, "BoostQuery")
        normalized = _rewrite_query_wrapper(normalized, "FieldExistsQuery", "field", "_exists_:")
        normalized = _rewrite_query_wrapper(normalized, "DocValuesFieldExistsQuery", "field", "_exists_:")
        if normalized == previous:
            break

    normalized = re.sub(r"FieldExistsQuery\s*\[\s*field=([^\]]+)\]", r"_exists_:\1", normalized)
    normalized = re.sub(r"DocValuesFieldExistsQuery\s*\[\s*field=([^\]]+)\]", r"_exists_:\1", normalized)
    normalized = re.sub(r"\bConstantScore(?:Query)?\b", "", normalized)
    normalized = LUCENE_HASH_PATTERN.sub(try_reinsert_lucene_phrase, normalized)
    return normalized.replace("@colon", ":")


def match(lucene: str, obj: dict[str, Any]):
    "Check if a given lucene query matches the given object"
    hash_key = sha256(lucene.encode()).hexdigest()

    # We cache the results back from ES, since we will frequently run the same validation queries over and over again.
    if (normalized_query := NORMALIZED_QUERY_CACHE.get(hash_key)) is None or TESTING:
        escaped_lucene = prepare_lucene_query(lucene)

        # Elasticsearch normalizes ambiguous boolean syntax in its explanation. Wildcards are replaced before
        # validation because Lucene 10 renders them as opaque AutomatonQuery internals instead of parseable terms.
        hit_collection = datastore().hit
        try:
            result = response_body(
                hit_collection.datastore.client.indices.validate_query(
                    q=escaped_lucene,
                    explain=True,
                    index=hit_collection.index_name,
                )
            )
        except (elasticsearch.exceptions.ConnectionError, elasticsearch.exceptions.ConnectionTimeout) as error:
            raise SearchRetryException(f"Unable to validate Lucene query: {error}") from error
        except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.RequestError) as error:
            raise SearchException(error_message(error)) from error
        except Exception as error:
            raise SearchException(f"Unable to validate Lucene query: {error}") from error

        if not result.get("valid", False):
            explanations = result.get("explanations", [])
            validation_error = (
                explanations[0].get("error") if explanations and isinstance(explanations[0], Mapping) else None
            )
            logger.error(
                "Invalid lucene query:\n%s",
                validation_error or result.get("error", "unknown validation error"),
            )
            return False

        explanations = result.get("explanations", [])
        if not explanations or not isinstance(explanations[0], Mapping):
            logger.error("Valid lucene query did not include an explanation")
            return False

        explanation = explanations[0].get("explanation")
        if not isinstance(explanation, str):
            logger.error("Valid lucene query included no parseable explanation")
            return False

        normalized_query = normalize_lucene_explanation(explanation)

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
