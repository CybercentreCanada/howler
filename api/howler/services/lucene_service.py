import fnmatch
import os
import re
import sys
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from typing import Any, Literal, Union

import elasticsearch
from luqum.parser import parser
from luqum.tree import AndOperation, BoolOperation, Phrase, Plus, Prohibit, Range, Regex, SearchField, Word
from luqum.utils import UnknownOperationResolver
from luqum.visitor import TreeVisitor
from pydantic import BaseModel

from howler.api import get_logger
from howler.common.exceptions import InvalidDataException
from howler.common.loader import datastore
from howler.config import redis
from howler.datastore.exceptions import SearchException, SearchRetryException
from howler.datastore.support.elastic import error_message, response_body
from howler.models.schema import build_properties
from howler.remote.datatypes.hash import Hash
from howler.utils.constants import TESTING
from howler.utils.dict_utils import flatten_deep
from howler.utils.lucene import coerce, normalize_phrase, try_parse_date, try_parse_ip, try_parse_number

logger = get_logger(__file__)

TRANSPORT_TIMEOUT = int(os.environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT", "10"))


@lru_cache(maxsize=1)
def _lowercase_fields(hit_model: type[BaseModel]) -> frozenset[str]:
    """Read the keyword normalizers once per finalized Hit class (including its plugin fields)."""
    properties, _ = build_properties(hit_model)
    return frozenset(
        path for path, spec in properties.items() if spec.get("normalizer") in {"lowercase", "lowercase_normalizer"}
    )


def _lucene_lower(value: str) -> str:
    """Lucene lowercases each code point independently (e.g. İ → i, and final Σ → σ)."""
    return value.lower() if value.isascii() else "".join(character.lower()[0] for character in value)


def _has_escaped_wildcard(term: str) -> bool:
    return r"\*" in term or r"\?" in term


def _escaped_wildcard_pattern(term: str) -> str:
    parts = []
    characters = iter(term)
    for character in characters:
        if character == "\\":
            literal = next(characters, "\\")
            parts.append(f"[{literal}]" if literal in "*?[" else literal)
        else:
            parts.append("[[]" if character == "[" else character)
    return "".join(parts)


def _match_escaped_wildcard(term: str, fields: Iterable[tuple[str, Any]], lowercase_fields: frozenset[str]) -> bool:
    """Compare against original text so literal '*' and '?' survive, applying only the field's own case rule."""
    pattern = _escaped_wildcard_pattern(term)
    for field, value in fields:
        lowercase = field in lowercase_fields
        field_pattern = _lucene_lower(pattern) if lowercase else pattern
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str) and fnmatch.fnmatchcase(_lucene_lower(item) if lowercase else item, field_pattern):
                return True
    return False


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
            low_datetime_result = datetime.fromtimestamp(int(low) / 1000, tz=datetime_result.tzinfo)

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
        field = context.get("field")
        if field == "_exists_":
            yield context["hit"].get(node.value) is not None
            return
        if isinstance(node, Word) and _has_escaped_wildcard(node.value):
            fields = context["hit"].items() if field is None else ((field, context["hit"].get(field)),)
            yield _match_escaped_wildcard(node.value, fields, context["lowercase_fields"])
            return

        sanitized_value = self.__sanitize_value(node.value)
        if field is None:
            yield any(value == sanitized_value for value in context["hit"].values())
        else:
            candidates = self.__build_candidates(context["hit"].get(field), context["term_type"])

            yield len(fnmatch.filter(candidates, sanitized_value)) > 0

    def visit_word(self, node: Phrase, context: dict[str, Any]):
        "Handle words"
        yield from self.__handle_word_or_phrase(node, {**context, "term_type": "word"})

    def visit_phrase(self, node: Phrase, context: dict[str, Any]):
        "Handle phrases"
        yield from self.__handle_word_or_phrase(node, {**context, "term_type": "phrase"})

    def visit_regex(self, node: Regex, context: dict[str, Any]):
        """An opaque Lucene automaton cannot establish a local match, even under NOT."""
        # Use the conservative truth value for this polarity. Other clauses may still establish an OR match.
        yield context.get("negated", False)

    def visit_prohibit(self, node: Prohibit, context: dict[str, Any]):
        "Handle NOT operation"
        child_context = {**context, "negated": not context.get("negated", False)}
        yield from (not entry for entry in self.generic_visit(node, child_context))


NORMALIZED_QUERY_CACHE: Hash[str] = Hash("normalized_queries_v2", redis)
LUCENE_HASH_PATTERN = re.compile(r'"([0-9a-f]{64})"|\b([0-9a-f]{64})\b')


def _unescaped_characters(value: str, start: int) -> Iterator[tuple[int, str]]:
    position = start
    while position < len(value):
        character = value[position]
        if character == "\\":
            position += 2
        else:
            yield position, character
            position += 1


def _unescaped_unquoted_characters(value: str, start: int = 0) -> Iterator[tuple[int, str]]:
    """Yield characters outside quotes, skipping Lucene escapes."""
    quoted = False
    for position, character in _unescaped_characters(value, start):
        if character == '"':
            quoted = not quoted
        elif not quoted:
            yield position, character


def _protect_term(value: str, tokens: dict[str, str] | None) -> str:
    key = sha256(value.encode()).hexdigest()
    if tokens is not None:
        tokens[key] = value
    return key


def _prepare_delimited(query: str, start: int, tokens: dict[str, str] | None) -> tuple[str, int]:
    delimiter = query[start]
    for position, character in _unescaped_characters(query, start + 1):
        if character != delimiter:
            continue
        literal = query[start : position + 1]
        if delimiter == "/":
            # Let Lucene validate the complete regexp, including its character classes and escapes.
            return literal, position + 1
        value = literal[1:-1]
        if not value or try_parse_date(value):
            return literal, position + 1
        if try_parse_ip(value):
            return literal.replace(":", "@colon"), position + 1
        # A quoted placeholder retains the token boundary even in queries such as field:"one"OR field:"two".
        return f'"{_protect_term(literal, tokens)}"', position + 1
    # Leave an unclosed literal for Elasticsearch to validate.
    return query[start:], len(query)


def _prepare_word(query: str, start: int, protect_wildcards: bool, tokens: dict[str, str] | None) -> tuple[str, int]:
    value_start = start
    end = len(query)
    for position, character in _unescaped_characters(query, start):
        if character.isspace() or character in '()[]{}"/':
            end = position
            break
        if character == ":" and value_start == start:
            value_start = position + 1

    word = query[start:end]
    value = query[value_start:end]
    # Lucene can render both an active '*' and a literal '\*' as '*'. Protect either spelling.
    if protect_wildcards and word != "*:*" and ("*" in value or "?" in value):
        word = query[start:value_start] + _protect_term(value, tokens)
    return word, end


def prepare_lucene_query(lucene: str, *, protect_wildcards: bool = True, tokens: dict[str, str] | None = None) -> str:
    """Protect Lucene terms, optionally recording their originals for this query's explanation."""
    parts = []
    position = 0
    while position < len(lucene):
        character = lucene[position]
        if character in '"/':
            part, position = _prepare_delimited(lucene, position, tokens)
        elif character in "[{":
            # A range (including mixed bounds) is opaque; its '*' endpoints are not wildcard terms.
            end = next(
                (i + 1 for i, c in _unescaped_unquoted_characters(lucene, position + 1) if c in "]}"), len(lucene)
            )
            part, position = lucene[position:end], end
        elif character.isspace() or character in "()]}+-!":
            part = character
            position += 1
        else:
            part, position = _prepare_word(lucene, position, protect_wildcards, tokens)
        parts.append(part)
    return "".join(parts)


def explain_query(query: str, index_name: str) -> dict[str, Any]:
    """Ask Elasticsearch to validate and explain a Lucene query for one index."""
    escaped_lucene = prepare_lucene_query(query, protect_wildcards=False)
    result = response_body(
        datastore().hit.datastore.client.indices.validate_query(
            q=escaped_lucene,
            explain=True,
            index=index_name,
        )
    )
    result.pop("_shards", None)
    for explanation in result.get("explanations", []):
        explanation.pop("index", None)
    return result


def _matching_parenthesis(value: str, opening: int) -> int | None:
    """Find the closing parenthesis for an unescaped opening parenthesis."""
    depth = 0
    for position, character in _unescaped_unquoted_characters(value, opening):
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
    for position, character in _unescaped_unquoted_characters(value):
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


def _rewrite_query_wrapper(value: str, wrapper: re.Pattern[str], argument_name: str | None, prefix: str) -> str:
    """Replace wrapped Lucene query text with its parseable inner query."""
    parts = []
    start = 0
    while match := wrapper.search(value, start):
        closing = _matching_parenthesis(value, match.end() - 1)
        if closing is None:
            break

        parts.append(value[start : match.start()])
        parts.append(prefix + _first_query_argument(value[match.end() : closing], argument_name))
        start = closing + 1

    parts.append(value[start:])
    return "".join(parts)


_EXISTS_WRAPPER = r"\b(?:DocValues)?FieldExistsQuery"
_QUERY_WRAPPERS = (
    (re.compile(r"\bIndexOrDocValuesQuery\("), "indexQuery", ""),
    (re.compile(r"\bConstantScore(?:Query)?\("), None, ""),
    (re.compile(r"\bBoostQuery\("), None, ""),
    (re.compile(_EXISTS_WRAPPER + r"\("), "field", "_exists_:"),
)
_BRACKETED_EXISTS_QUERY = re.compile(_EXISTS_WRAPPER + r"\s*\[\s*field=([^\]]+)\]")
_OPAQUE_AUTOMATON = re.compile(
    r"\bAutomatonQuery\s*\{\s*org\.apache\.lucene\.util\.automaton\.Automaton@[0-9a-f]+\s*\}"
)


def normalize_lucene_explanation(explanation: str, tokens: Mapping[str, str] | None = None) -> str:
    """Convert Elasticsearch/Lucene explain text to the stable query syntax we parse.

    Lucene 10 changed several implementation details in explain strings and can
    nest ``IndexOrDocValuesQuery`` wrappers more deeply.  Query wrappers are
    removed with balanced-parenthesis parsing instead of regexes so ranges,
    boolean queries, and nested wrappers remain intact.
    """
    normalized = explanation.strip()
    # Lucene returns an object identity for some regexes. Retain one Regex leaf when parsing the boolean query.
    normalized = _OPAQUE_AUTOMATON.sub("/AutomatonQuery/", normalized)

    for _ in range(8):
        previous = normalized
        for wrapper, argument_name, prefix in _QUERY_WRAPPERS:
            normalized = _rewrite_query_wrapper(normalized, wrapper, argument_name, prefix)
        if normalized == previous:
            break

    normalized = _BRACKETED_EXISTS_QUERY.sub(r"_exists_:\1", normalized)
    normalized = re.sub(r"\bConstantScore(?:Query)?\b", "", normalized)
    normalized = normalized.replace("@colon", ":")
    if tokens:
        normalized = LUCENE_HASH_PATTERN.sub(lambda match: tokens.get(match[1] or match[2], match[0]), normalized)
    return normalized


def match(lucene: str, obj: dict[str, Any]):
    "Check if a given lucene query matches the given object"
    hash_key = sha256(lucene.encode()).hexdigest()

    # We cache the results back from ES, since we will frequently run the same validation queries over and over again.
    if (normalized_query := NORMALIZED_QUERY_CACHE.get(hash_key)) is None or TESTING:
        tokens: dict[str, str] = {}
        escaped_lucene = prepare_lucene_query(lucene, tokens=tokens)

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

        normalized_query = normalize_lucene_explanation(explanation, tokens)

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
        lowercase_fields = (
            _lowercase_fields(datastore().ds.get_models()["hit"])
            if _has_escaped_wildcard(normalized_query)
            else frozenset()
        )
        return LuceneProcessor(track_parents=True).visit(
            tree, {"hit": flatten_deep(obj), "lowercase_fields": lowercase_fields}
        )
    except Exception:
        logger.exception("Exception on processing lucene:")
        return False


if __name__ == "__main__":
    hit = datastore().hit.search("howler.id:*", rows=1, as_obj=False)["items"][0]

    print(match(sys.argv[1], hit))  # noqa: T201
