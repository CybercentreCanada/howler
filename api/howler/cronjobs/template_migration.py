from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.date import DateTrigger

from howler.common.logging import get_logger
from howler.odm.models.template import Template
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


def execute():
    """Delete any pinned views that no longer exist"""
    from howler.common.loader import datastore

    # Initialize datastore
    ds = datastore()

    templates: list[Template] = ds.template.search("analytic:*")["items"]

    for template in templates:
        template.query = f'howler.analytic:"{sanitize_lucene_query(template.analytic)}"'
        template.name = template.analytic

        if template.detection:
            template.query += f' AND howler.detection:"{sanitize_lucene_query(template.detection)}"'
            template.name += f'  - {template.detection or "Any"}'

        template.analytic = None
        template.detection = None


def setup_job(sched: BaseScheduler):
    """Initialize the view cleanup job"""
    logger.debug("Initializing template migration")

    if sched.get_job("template_migration"):
        logger.debug("template_migration already running!")
        return

    sched.add_job(id="template_migration", func=execute, trigger=DateTrigger())
    logger.debug("Initialization complete")
