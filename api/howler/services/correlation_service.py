"""Match records to case rules, for both live ingestion and explicit backfills.

Ingestion producers add record IDs to a persistent Redis queue. The worker groups
queued IDs into bounded batches and asks ``process_batch`` to evaluate them. Normal
ingestion checks all enabled, non-expired rules; backfill queue entries include a
rule ID so only the selected rule is evaluated. Backfills first search for historical
matches (respecting the requesting user's access), then enqueue IDs for the same
worker to handle. All case and backing-record updates therefore use one correlation
path, regardless of how an ID entered the queue.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

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
from howler.odm.models.user import User
from howler.remote.datatypes.queues.named import NamedQueue
from howler.services import case_service, comms_service, search_service
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)

BATCH_SIZE: int = config.system.correlation.batch_size
BATCH_TIMEOUT: int = config.system.correlation.batch_timeout


def _normalize_utc(ts: datetime) -> datetime:
    """Normalize a datetime to UTC, assuming naive timestamps are UTC."""
    # Datastore timestamps are normally timezone-aware, but treating naive values as
    # UTC keeps expiry comparisons deterministic for older or test records.
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def get_backfill_rule(case_id: str, rule_id: str, user: User, since_value: object) -> tuple[CaseRule, datetime]:
    """Validate case access, rule selection, and the backfill timestamp."""
    # Use the service's access-aware case getter so rule details aren't exposed for
    # cases the caller cannot read; only enabled rules can be explicitly backfilled.
    case = case_service.get_case(case_id, as_odm=True, version=False, user=user)
    if not case:
        raise NotFoundException(f"Case {case_id} not found")

    rule = next((candidate for candidate in case.rules if candidate.rule_id == rule_id), None)
    if rule is None:
        raise NotFoundException(f"Rule {rule_id} not found in case {case_id}")
    if not rule.enabled:
        raise InvalidDataException("Only enabled rules can be backfilled")

    if not isinstance(since_value, str) or not since_value.strip():
        raise InvalidDataException("A valid 'since' datetime is required")

    try:
        since = datetime.fromisoformat(since_value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidDataException("A valid 'since' datetime is required") from error

    # UI requests include an ISO timestamp with offset; accept naive ISO strings as
    # UTC as well, and normalize the returned boundary before building the query.
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    return rule, since.astimezone(timezone.utc)


# The shared persistent queue lets web/API ingestion producers hand work to the
# background correlation worker without doing Elasticsearch and case writes inline.
class CorrelationJob(TypedDict):
    """One queued record, optionally restricted to a single correlation rule."""

    id: str
    rule_id: str | None


_ingestion_queue: NamedQueue[CorrelationJob | str] | None = None


def _get_ingestion_queue() -> NamedQueue[CorrelationJob | str]:
    """Return the shared ingestion queue, creating it on first use."""
    global _ingestion_queue

    if _ingestion_queue is None:
        # Keep one queue object per process; Redis itself is shared by API workers
        # and the correlation worker through the configured persistent connection.
        _ingestion_queue = NamedQueue(
            CORRELATION_QUEUE_NAME,
            host=config.core.redis.persistent.host,
            port=config.core.redis.persistent.port,
            private=False,
        )

    return _ingestion_queue


def _validate_correlation_job(item: object) -> CorrelationJob | None:
    """Normalize legacy string entries and reject malformed queue messages."""
    if isinstance(item, str):
        # Queue contents can outlive a deploy. Upgrade IDs written by older
        # producers into the current job shape and preserve global rule matching.
        return {"id": item, "rule_id": None} if item else None

    if not isinstance(item, dict):
        logger.warning("Skipping invalid correlation queue item: %r", item)
        return None

    record_id = item.get("id")
    rule_id = item.get("rule_id")
    if not isinstance(record_id, str) or not record_id or (rule_id is not None and not isinstance(rule_id, str)):
        logger.warning("Skipping invalid correlation queue item: %r", item)
        return None

    return {"id": record_id, "rule_id": rule_id}


def _resolve_backing_object(
    item_type: Literal["hit", "event"],
    record_id: str,
    backing_cache: dict[tuple[Literal["hit", "event"], str], tuple[Hit | Event | None, str]],
) -> tuple[Hit | Event, str]:
    """Fetch (and cache) the hit/event backing a correlation match, across the whole batch.

    Raises:
        NotFoundException: If the backing hit/event does not exist.
    """
    # A record ID is only unique within its index, so cache hit and event objects
    # separately. The cache is shared for the whole batch to avoid repeat reads.
    key = (item_type, record_id)
    if key not in backing_cache:
        ds = datastore()
        if item_type == RuleIndexTypes.EVENT:
            backing_cache[key] = ds.event.get(key=record_id, as_obj=True, version=True)
        elif item_type == RuleIndexTypes.HIT:
            backing_cache[key] = ds.hit.get(record_id, as_obj=True, version=True)
        else:
            raise InvalidDataException(f"Invalid index type {item_type} provided. Must be one of hit,event")

    backing_obj, backing_obj_version = backing_cache[key]
    if not backing_obj:
        raise NotFoundException(f"{item_type.capitalize()} {record_id} not found, cannot be added to case")

    return backing_obj, backing_obj_version


def _add_record_to_case(
    case: Case,
    record: dict,
    rule: CaseRule,
    backing_cache: dict[tuple[Literal["hit", "event"], str], tuple[Hit | Event | None, str]],
) -> tuple[Literal["hit", "event"], str] | None:
    """Append a single matching record to a case, in memory only (no datastore writes).

    Mirrors the validation/dispatch behaviour of ``case_service.append_case_item`` for hit
    and event items, but mutates ``case.items`` directly instead of saving the case (and its
    backing hit/event) on every call.

    Returns:
        True if the record was added to the case.
    """
    # Search results identify their logical index as well as the Howler ID; both are
    # needed to create a case item and retrieve its backing record.
    record_id = record["howler"]["id"]
    item_type = record.get("__index", "hit")

    # Rule destinations are Mustache templates, allowing matched fields to group
    # records into folders. The final path segment becomes the item's display name.
    rendered_path = chevron.render(rule.destination, record)
    try:
        path, name = rendered_path.rsplit("/", maxsplit=1)
    except ValueError:
        path = None
        name = rendered_path

    try:
        backing_obj, backing_obj_version = _resolve_backing_object(item_type, record_id, backing_cache)

        parent = case_service.get_parent_from_path(case, path, create_if_missing=True)

        item = CaseItem({"type": item_type, "value": record_id, "parent": parent.id if parent else None, "name": name})
        if item.name is None:
            item.name = item.value

        # Preserve useful names where possible, but fall back to an ID-suffixed name
        # if another item already occupies the destination/name combination.
        if case_service.check_conflicts(case, item):
            item.name = f"{item.name} ({item.value})" if item.name else item.value

            if case_service.check_conflicts(case, item):
                return None

        # Case items inherit the backing record's classification and the reverse
        # relation is maintained on that record for navigation from either side.
        item.classification = backing_obj.classification
        case.items.append(item)

        if case_service.add_backreference(backing_obj, case.case_id):
            return (item_type, record_id)

        return None
    except InvalidDataException:
        logger.info("Record %s already exists in case %s or is invalid, skipping", record_id, case.case_id)
    except NotFoundException:
        logger.warning("Case %s or record %s not found during correlation", case.case_id, record_id)
    except Exception:  # pragma: no cover
        logger.exception("Failed to add record %s to case %s", record_id, case.case_id)

    return None


def enqueue_for_correlation(ids: list[str], rule_id: str | None = None) -> None:
    """Enqueue record IDs for correlation processing.

    Args:
        ids: List of record IDs to enqueue for correlation.
        rule_id: Optional rule ID to restrict correlation to.

    Raises:
        HowlerRuntimeError: If enqueueing fails.
    """
    try:
        # Every queue entry has the same shape. A null rule_id means the worker
        # should evaluate the record against all currently active rules.
        jobs: list[CorrelationJob] = [{"id": record_id, "rule_id": rule_id} for record_id in ids]
        _get_ingestion_queue().push(*jobs)
    except Exception:
        logger.exception("Error on queuing for correlation")


def count_backfill_matches(case_id: str, rule_id: str, since_value: object, user: User) -> int:
    """Count accessible records matching a case rule since the requested timestamp."""
    rule, since = get_backfill_rule(case_id, rule_id, user, since_value)
    # SearchService applies classification access control for this user. Tracking
    # the full total ensures the confirmation count is exact even above 10,000.
    result = search_service.search(
        indexes=rule.indexes or [RuleIndexTypes.HIT],
        query=rule.query,
        filters=[f'timestamp:["{since.isoformat()}" TO *]'],
        rows=0,
        track_total_hits=True,
        user=user,
    )
    return result["total"]


def enqueue_backfill(case_id: str, rule_id: str, since_value: object, user: User) -> int:
    """Stream matching accessible records into the rule-scoped correlation queue."""
    rule, since = get_backfill_rule(case_id, rule_id, user, since_value)
    indexes = rule.indexes or [RuleIndexTypes.HIT]
    query = rule.query
    count = 0
    # Deep paging keeps memory bounded for large historical ranges. Only fetch the
    # IDs needed by the worker rather than loading complete alert documents here.
    page = search_service.search(
        indexes=indexes,
        query=query,
        filters=[f'timestamp:["{since.isoformat()}" TO *]'],
        rows=500,
        fl="howler.id",
        deep_paging_id="*",
        user=user,
    )

    while True:
        ids = [item.get("howler", {}).get("id") for item in page["items"]]
        ids = [record_id for record_id in ids if isinstance(record_id, str)]
        if ids:
            # Enqueue each page as it arrives; this lets the worker begin processing
            # immediately and prevents the API request from accumulating all matches.
            enqueue_for_correlation(ids, rule_id=rule_id)
            count += len(ids)

        next_page = page.get("next_deep_paging_id")
        if not next_page:
            break

        page = search_service.search(
            indexes=indexes,
            query=query,
            filters=[f'timestamp:["{since.isoformat()}" TO *]'],
            rows=500,
            fl="howler.id",
            deep_paging_id=next_page,
            user=user,
        )

    return count


def get_active_rules(rule_id: str | None = None) -> list[tuple[str, CaseRule]]:  # noqa: C901
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
    # Backfill passes rule_id to bypass the normal “currently active” timeframe
    # check, while regular ingestion uses the default and only sees live rules.
    ds = datastore()
    now = datetime.now(timezone.utc)
    active: list[tuple[str, CaseRule]] = []

    # Only fetch cases that actually have rules.
    for _case in ds.case.stream_search("_exists_:rules.rule_id"):
        # Lazily compute last resolved time only if needed by at least one rule.
        _last_resolved: datetime | None = None
        _last_resolved_computed = False

        for rule in _case.rules:
            if rule_id is not None and rule.rule_id != rule_id:
                continue

            if not rule.enabled:
                continue

            # Explicit backfills intentionally run the selected rule even if its
            # normal creation/resolution timeframe has elapsed.
            if rule_id is not None:
                active.append((_case.case_id, rule))
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
                # For these rules, expiry is paused until the case has a resolution
                # timestamp; look it up only once for cases with this rule type.
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
def process_batch(record_ids: list[str], rule_id: str | None = None) -> int:  # noqa: C901
    """Evaluate all active case rules against a batch of record IDs.

    For each rule, a single Elasticsearch query is run against the indexes
    specified by the rule (hit, event, or both) to find which of the
    given records match. Matching records are accumulated in memory against
    their owning case (at the rule's Mustache-rendered destination path), and
    every touched case is written to the datastore once, in a single bulk
    transaction, rather than saving on every match.

    Args:
        record_ids: List of record IDs (hit or event) to evaluate.
        rule_id: Optional rule ID to restrict correlation to.

    Returns:
        The number of records successfully added to cases.
    """
    if not record_ids:
        return 0

    ds = datastore()

    # Selecting rules here keeps queue messages small and means an ingestion batch
    # automatically sees rules created after the record was queued.
    rules = get_active_rules(rule_id)
    if not rules:
        return 0

    # The ID filter restricts each rule's query to this batch, so rules can be
    # evaluated with one search each rather than one search per record.
    id_filter = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in record_ids)})"
    added = 0

    # Cases and their backing hit/event objects are fetched once per batch and mutated in
    # memory; they're only written to the datastore after every rule has been evaluated.
    case_cache: dict[str, Case | None] = {}
    case_original_item_counts: dict[str, int] = {}
    backing_cache: dict[tuple[Literal["hit", "event"], str], tuple[Hit | Event | None, str]] = {}
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
            # SearchService returns each result's logical index and full source;
            # full records are needed to render the rule's destination template.
            results = search_service.search(
                indexes=indexes, query=rule.query, filters=[id_filter], rows=len(record_ids)
            )
        except Exception:
            logger.exception("ES query failed for rule %s (case %s): %s", rule.rule_id, case_id, rule.query)
            continue

        for record in results["items"]:
            if result := _add_record_to_case(case, record, rule, backing_cache):
                dirty_backing_keys.add(result)
                added += 1

    # Update reverse links separately from case documents, batching writes per
    # collection so the number of datastore operations doesn't grow per match.
    backing_bulk_plans = {item_type: ds[item_type].get_bulk_plan() for item_type, _ in dirty_backing_keys}

    for item_type, record_id in dirty_backing_keys:
        backing_obj = backing_cache[(item_type, record_id)][0]
        if backing_obj:
            backing_bulk_plans[item_type].add_update_operation(record_id, backing_obj, fields=["howler.related"])

    for item_type, bulk_plan in backing_bulk_plans.items():
        if not ds[item_type].bulk(bulk_plan):
            raise HowlerRuntimeError("Bulk backing record update reported errors while flushing correlation batch")

    # Cases are only considered modified when an item was actually appended;
    # duplicate matches are ignored by _add_record_to_case.
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

    # Notify connected clients after persistence so case views can refresh promptly.
    for case in modified_cases:
        comms_service.emit("cases", {"case": case.as_primitives()})

    return added


def run_worker() -> None:  # pragma: no cover – long-running loop, tested via process_batch
    """Block on the ingestion queue and process batches of record IDs.

    Accumulates up to ``BATCH_SIZE`` IDs or flushes after ``BATCH_TIMEOUT``
    seconds, whichever comes first.
    """
    # This loop is deliberately long-lived: producers write to Redis, and this
    # consumer batches work to amortize rule searches and datastore updates.
    queue = _get_ingestion_queue()
    logger.info("Correlation worker started (batch_size=%d, timeout=%ds)", BATCH_SIZE, BATCH_TIMEOUT)

    batch: list[CorrelationJob] = []

    while True:
        try:
            item: CorrelationJob | str | None = queue.pop(timeout=BATCH_TIMEOUT)

            if item is not None:
                if job := _validate_correlation_job(item):
                    batch.append(job)

            if len(batch) > 0 and (len(batch) % 10 == 0 or len(batch) >= BATCH_SIZE):
                logger.info("Batch size: %s", len(batch))

            # Process when the configured batch fills, or flush a partial batch
            # after an idle timeout so low-volume traffic doesn't wait indefinitely.
            if len(batch) >= BATCH_SIZE or (item is None and batch):
                finalized_batch = [*batch]
                batch = []

                logger.debug("Processing correlation batch of %d hit(s)", len(finalized_batch))
                try:
                    # A batch can contain regular ingestion and backfill jobs.
                    # Separate them so each group gets the correct rule selection.
                    grouped_ids: dict[str | None, list[str]] = {}
                    for queued_item in finalized_batch:
                        grouped_ids.setdefault(queued_item["rule_id"], []).append(queued_item["id"])

                    for queued_rule_id, record_ids in grouped_ids.items():
                        added = process_batch(record_ids, rule_id=queued_rule_id)
                        logger.info(
                            "Correlation batch complete: %d case item(s) added for %d record(s)",
                            added,
                            len(record_ids),
                        )
                except Exception:
                    logger.exception("Error processing correlation batch %s", finalized_batch)
        except Exception:
            logger.exception("Unexpected error in correlation worker loop")
