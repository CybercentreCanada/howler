"""Correlation service — matches newly ingested records against active case rules.

The public API consists of three functions:

- ``get_active_rules()`` — fetch all enabled, non-expired case rules.
- ``process_batch(record_ids)`` — evaluate active rules against a batch of record IDs.
- ``run_worker()`` — long-running loop that drains the ingestion queue and
  calls ``process_batch`` in debounced batches.
"""

from datetime import datetime, timezone

import chevron
from opentelemetry import trace

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.case import CaseRule, RuleIndexTypes
from howler.odm.models.config import config
from howler.remote.datatypes.queues.named import NamedQueue
from howler.services import case_service, search_service
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)

BATCH_SIZE: int = config.system.correlation.batch_size
BATCH_TIMEOUT: int = config.system.correlation.batch_timeout


def get_active_rules() -> list[tuple[str, CaseRule]]:
    """Return all active (enabled, non-expired) rules across every case.

    Returns:
        A list of ``(case_id, rule)`` tuples for rules that should be evaluated.
    """
    ds = datastore()
    now = datetime.now(timezone.utc)
    active: list[tuple[str, CaseRule]] = []

    # Only fetch cases that actually have rules.
    for _case in ds.case.stream_search("_exists_:rules.rule_id"):
        for rule in _case.rules:
            if not rule.enabled:
                continue

            if rule.timeframe is not None:
                try:
                    expiry = datetime.fromisoformat(str(rule.timeframe))
                    if expiry <= now:
                        continue
                except (ValueError, TypeError):
                    logger.warning("Invalid timeframe on rule %s in case %s", rule.rule_id, _case.case_id)
                    continue

            active.append((_case.case_id, rule))

    return active


@tracer.start_as_current_span(f"{__name__}.process_batch")
def process_batch(record_ids: list[str]) -> int:
    """Evaluate all active case rules against a batch of record IDs.

    For each rule, a single Elasticsearch query is run against the indexes
    specified by the rule (hit, observable, or both) to find which of the
    given records match. Matching records are appended to the owning case at
    the rule's (Mustache-rendered) destination path.

    Args:
        record_ids: List of record IDs (hit or observable) to evaluate.

    Returns:
        The number of records successfully added to cases.
    """
    if not record_ids:
        return 0

    ds = datastore()

    # Ensure recently written data is searchable before querying.
    ds.case.commit()
    ds.hit.commit()

    rules = get_active_rules()
    if not rules:
        return 0

    id_filter = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in record_ids)})"
    added = 0

    for case_id, rule in rules:
        indexes: list[str] = list(rule.indexes) if rule.indexes else [RuleIndexTypes.HIT]

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
            record_id = record["howler"]["id"]
            item_type = record.get("__index", "hit")
            rendered_path = chevron.render(rule.destination, record)

            try:
                case_service.append_case_item(
                    case_id,
                    item_type=item_type,
                    item_value=record_id,
                    item_path=rendered_path,
                )
                added += 1
            except InvalidDataException:
                logger.debug("Record %s already exists in case %s, skipping", record_id, case_id)
            except NotFoundException:
                logger.warning("Case %s or record %s not found during correlation", case_id, record_id)
            except Exception:
                logger.exception("Failed to add record %s to case %s", record_id, case_id)

    return added


def _build_queue() -> NamedQueue[str]:
    """Create the NamedQueue backed by persistent Redis."""
    return NamedQueue(
        "howler.ingestion_queue",
        host=config.core.redis.persistent.host,
        port=config.core.redis.persistent.port,
        private=False,
    )


def run_worker() -> None:  # pragma: no cover – long-running loop, tested via process_batch
    """Block on the ingestion queue and process batches of record IDs.

    Accumulates up to ``BATCH_SIZE`` IDs or flushes after ``BATCH_TIMEOUT``
    seconds, whichever comes first.
    """
    queue = _build_queue()
    logger.info("Correlation worker started (batch_size=%d, timeout=%ds)", BATCH_SIZE, BATCH_TIMEOUT)

    batch: list[str] = []

    while True:
        try:
            item: str | None = queue.pop(blocking=True, timeout=BATCH_TIMEOUT)

            if item is not None:
                batch.append(item)

            if len(batch) >= BATCH_SIZE or (item is None and batch):
                logger.debug("Processing correlation batch of %d hit(s)", len(batch))
                try:
                    added = process_batch(batch)
                    logger.info("Correlation batch complete: %d/%d hit(s) added", added, len(batch))
                except Exception:
                    logger.exception("Error processing correlation batch")
                finally:
                    batch = []
        except Exception:
            logger.exception("Unexpected error in correlation worker loop")
