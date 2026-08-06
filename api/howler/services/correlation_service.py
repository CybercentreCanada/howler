"""Correlation service — matches newly ingested records against active case rules.

The public API consists of three functions:

- ``get_active_rules()`` — fetch all enabled, non-expired case rules.
- ``process_batch(record_ids)`` — evaluate active rules against a batch of record IDs.
- ``run_worker()`` — long-running loop that drains the ingestion queue and
  calls ``process_batch`` in debounced batches.
"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal

import chevron
from opentelemetry import trace

from howler.common.exceptions import HowlerRuntimeError, InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.config import CORRELATION_QUEUE_NAME
from howler.odm.models.case import Case, CaseItem, CaseRule, RuleIndexTypes
from howler.odm.models.config import config
from howler.odm.models.event import Event
from howler.odm.models.hit import Hit
from howler.remote.datatypes.queues.named import NamedQueue
from howler.services import case_service, comms_service, search_service
from howler.utils.str_utils import sanitize_lucene_query

if TYPE_CHECKING:
    pass


logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)

BATCH_SIZE: int = config.system.correlation.batch_size
BATCH_TIMEOUT: int = config.system.correlation.batch_timeout


def _normalize_utc(ts: datetime) -> datetime:
    """Normalize a datetime to UTC, assuming naive timestamps are UTC."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


# Persistent queue for the correlation worker to consume newly ingested hit IDs.
_ingestion_queue: NamedQueue[str] | None = None


def _get_ingestion_queue() -> NamedQueue[str]:
    """Return the shared ingestion queue, creating it on first use."""
    global _ingestion_queue

    if _ingestion_queue is None:
        _ingestion_queue = NamedQueue(
            CORRELATION_QUEUE_NAME,
            host=config.core.redis.persistent.host,
            port=config.core.redis.persistent.port,
            private=False,
        )

    return _ingestion_queue


def _resolve_backing_object(
    item_type: Literal["hit", "event"],
    record_id: str,
    backing_cache: dict[tuple[Literal["hit", "event"], str], Hit | Event | None],
) -> Hit | Event:
    """Fetch (and cache) the hit/event backing a correlation match, across the whole batch.

    Raises:
        NotFoundException: If the backing hit/event does not exist.
    """
    key = (item_type, record_id)
    if key not in backing_cache:
        ds = datastore()
        if item_type == RuleIndexTypes.EVENT:
            backing_cache[key] = ds.event.get(key=record_id)
        elif item_type == RuleIndexTypes.HIT:
            backing_cache[key] = ds.hit.get(record_id)
        else:
            raise InvalidDataException(f"Invalid index type {item_type} provided. Must be one of hit,event")

    backing_obj = backing_cache[key]
    if backing_obj is None:
        raise NotFoundException(f"{item_type.capitalize()} {record_id} not found, cannot be added to case")

    return backing_obj


def _add_record_to_case(
    case: Case,
    case_id: str,
    record: dict,
    rule: CaseRule,
    backing_cache: dict[tuple[Literal["hit", "event"], str], Hit | Event | None],
) -> tuple[Literal["hit", "event"], str] | None:
    """Append a single matching record to a case, in memory only (no datastore writes).

    Mirrors the validation/dispatch behaviour of ``case_service.append_case_item`` for hit
    and event items, but mutates ``case.items`` directly instead of saving the case (and its
    backing hit/event) on every call.

    Returns:
        True if the record was added to the case.
    """
    record_id = record["howler"]["id"]
    item_type = record.get("__index", "hit")

    rendered_path = chevron.render(rule.destination, record)
    try:
        path, name = rendered_path.rsplit("/", maxsplit=1)
    except ValueError:
        path = None
        name = rendered_path

    try:
        backing_obj = _resolve_backing_object(item_type, record_id, backing_cache)

        parent = case_service.get_parent_from_path(case, path, create_if_missing=True, persist=False)

        item = CaseItem({"type": item_type, "value": record_id, "parent": parent.id if parent else None, "name": name})
        if item.name is None:
            item.name = item.value

        if case_service.check_conflicts(case, item):
            item.name = f"{item.name} ({item.value})" if item.name else item.value

            if case_service.check_conflicts(case, item):
                return None

        item.classification = backing_obj.classification
        case.items.append(item)

        if case_service.add_backreference(backing_obj, case_id):
            return (item_type, record_id)

        return None
    except InvalidDataException:
        logger.info("Record %s already exists in case %s or is invalid, skipping", record_id, case_id)
    except NotFoundException:
        logger.warning("Case %s or record %s not found during correlation", case_id, record_id)
    except Exception:  # pragma: no cover
        logger.exception("Failed to add record %s to case %s", record_id, case_id)

    return None


def enqueue_for_correlation(ids: list[str]) -> None:
    """Enqueue record IDs for correlation processing.

    Args:
        ids: List of record IDs to enqueue for correlation.

    Raises:
        HowlerRuntimeError: If enqueueing fails.
    """
    try:
        _get_ingestion_queue().push(*ids)
    except Exception:
        logger.exception("Error on queuing for correlation")


def get_active_rules() -> list[tuple[str, CaseRule]]:  # noqa: C901
    """Return all active (enabled, non-expired) rules across every case.

    A rule's ``timeframe`` is an optional integer representing how many days
    the rule stays active. When ``expire_after_resolved`` is False (default),
    the countdown starts from ``rule.created_at``. When True, it starts from
    the case's most recent resolution time (if the case has never been resolved
    the timer has not started and the rule remains active).

    If ``timeframe`` is None the rule never expires.

    Returns:
        A list of ``(case_id, rule)`` tuples for rules that should be evaluated.
    """
    ds = datastore()
    now = datetime.now(timezone.utc)
    active: list[tuple[str, CaseRule]] = []

    # Only fetch cases that actually have rules.
    for _case in ds.case.stream_search("_exists_:rules.rule_id"):
        # Lazily compute last resolved time only if needed by at least one rule.
        _last_resolved: datetime | None = None
        _last_resolved_computed = False

        for rule in _case.rules:
            if not rule.enabled:
                continue

            if rule.timeframe is None:
                # No expiry configured — rule is always active.
                active.append((_case.case_id, rule))
                continue

            # Skip rules whose timeframe is not a valid positive integer.
            if isinstance(rule.timeframe, bool) or not isinstance(rule.timeframe, int) or rule.timeframe <= 0:
                logger.warning("Skipping rule %s with invalid timeframe: %r", rule.rule_id, rule.timeframe)
                continue

            start: datetime
            if not rule.expire_after_resolved:
                start = datetime.fromisoformat(str(rule.created_at).replace("Z", "+00:00"))
            else:
                # Timer starts from last resolution.
                if not _last_resolved_computed:
                    _last_resolved = case_service.get_last_resolved_time(_case)
                    _last_resolved_computed = True

                if _last_resolved is None:
                    # Case not yet resolved — timer hasn't started.
                    active.append((_case.case_id, rule))
                    continue

                start = _normalize_utc(_last_resolved)

            expiry = start + timedelta(days=rule.timeframe)
            if expiry > now:
                active.append((_case.case_id, rule))

    return active


@tracer.start_as_current_span(f"{__name__}.process_batch")
def process_batch(record_ids: list[str]) -> int:  # noqa: C901
    """Evaluate all active case rules against a batch of record IDs.

    For each rule, a single Elasticsearch query is run against the indexes
    specified by the rule (hit, event, or both) to find which of the
    given records match. Matching records are accumulated in memory against
    their owning case (at the rule's Mustache-rendered destination path), and
    every touched case is written to the datastore once, in a single bulk
    transaction, rather than saving on every match.

    Args:
        record_ids: List of record IDs (hit or event) to evaluate.

    Returns:
        The number of records successfully added to cases.
    """
    if not record_ids:
        return 0

    ds = datastore()

    rules = get_active_rules()
    if not rules:
        return 0

    id_filter = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in record_ids)})"
    added = 0

    # Cases and their backing hit/event objects are fetched once per batch and mutated in
    # memory; they're only written to the datastore after every rule has been evaluated.
    case_cache: dict[str, Case | None] = {}
    case_original_item_counts: dict[str, int] = {}
    backing_cache: dict[tuple[Literal["hit", "event"], str], Hit | Event | None] = {}
    dirty_backing_keys: set[tuple[Literal["hit", "event"], str]] = set()

    for case_id, rule in rules:
        indexes: list[str] = list(rule.indexes) if rule.indexes else [RuleIndexTypes.HIT]

        if case_id not in case_cache:
            case = ds.case.get(case_id)
            if case:
                case_original_item_counts[case_id] = len(case.items)

            case_cache[case_id] = case

        case = case_cache[case_id]
        if case is None:
            logger.warning("Case %s not found during correlation", case_id)
            continue

        try:
            results = search_service.search(
                indexes=indexes,
                query=rule.query,
                filters=[id_filter],
                rows=len(record_ids),
            )
        except Exception:
            logger.exception("ES query failed for rule %s (case %s): %s", rule.rule_id, case_id, rule.query)
            continue

        for record in results["items"]:
            if result := _add_record_to_case(case, case_id, record, rule, backing_cache):
                dirty_backing_keys.add(result)
                added += 1

    backing_bulk_plans = {item_type: ds[item_type].get_bulk_plan() for item_type, _ in dirty_backing_keys}

    for item_type, record_id in dirty_backing_keys:
        backing_obj = backing_cache[(item_type, record_id)]
        if backing_obj is not None:
            backing_bulk_plans[item_type].add_update_operation(record_id, backing_obj, fields=["howler.related"])

    for item_type, bulk_plan in backing_bulk_plans.items():
        if not ds[item_type].bulk(bulk_plan):
            raise HowlerRuntimeError("Bulk backing record update reported errors while flushing correlation batch")

    modified_cases = [
        case for cid, case in case_cache.items() if case and len(case.items) != case_original_item_counts[cid]
    ]
    bulk_plan = ds.case.get_bulk_plan()

    logger.info("Modified cases: %s", len(modified_cases))
    if modified_cases:
        for case in modified_cases:
            case_service.recompute_case_metadata(case)
            # Partial update: only touch fields derived from items, so concurrent user edits
            # to the case (title, summary, rules, ...) aren't clobbered by a stale in-memory copy.
            bulk_plan.add_update_operation(case.case_id, case, fields=["items", "targets", "threats", "indicators"])

    if bulk_plan.empty:
        logger.info(
            "Bulk plan for batch %s is empty.", f"({', '.join(record_ids[:5])}{', ...' if len(record_ids) > 5 else ''})"
        )
    else:
        logger.info("Exexcuting bulk plan (%s operations)", len(bulk_plan.operations))

        if not ds.case.bulk(bulk_plan, refresh="wait_for"):
            raise HowlerRuntimeError("Bulk case update reported errors while flushing correlation batch")

    for case in modified_cases:
        comms_service.emit("cases", {"case": case.as_primitives()})

    return added


def run_worker() -> None:  # pragma: no cover – long-running loop, tested via process_batch
    """Block on the ingestion queue and process batches of record IDs.

    Accumulates up to ``BATCH_SIZE`` IDs or flushes after ``BATCH_TIMEOUT``
    seconds, whichever comes first.
    """
    queue = _get_ingestion_queue()
    logger.info("Correlation worker started (batch_size=%d, timeout=%ds)", BATCH_SIZE, BATCH_TIMEOUT)

    batch: list[str] = []

    while True:
        try:
            item: str | None = queue.pop(timeout=BATCH_TIMEOUT)

            if item is not None:
                batch.append(item)

            if len(batch) > 0:
                logger.info("Batch size: %s", len(batch))

            if len(batch) >= BATCH_SIZE or (item is None and batch):
                finalized_batch = [*batch]
                batch = []

                logger.debug("Processing correlation batch of %d hit(s)", len(finalized_batch))
                try:
                    added = process_batch(finalized_batch)
                    logger.info(
                        "Correlation batch complete: %d case item(s) added for %d record(s)",
                        added,
                        len(finalized_batch),
                    )
                except Exception:
                    logger.exception("Error processing correlation batch %s", ", ".join(finalized_batch))
        except Exception:
            logger.exception("Unexpected error in correlation worker loop")
