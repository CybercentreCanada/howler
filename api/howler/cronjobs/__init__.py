import importlib
import os
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

from howler.common.logging import get_logger

logger = get_logger(__file__)

scheduler = BackgroundScheduler(timezone=timezone(os.getenv("SCHEDULER_TZ", "America/Toronto")))


def setup_jobs():
    "Dynamically import and initialize all cronjobs in this folder"
    module_path = Path(__file__).parent
    modules_to_import = [_file for _file in os.listdir(module_path) if _file.endswith(".py") and _file != "__init__.py"]

    for module in modules_to_import:
        try:
            job = importlib.import_module(f"howler.cronjobs.{module.replace('.py', '')}")

            job.setup_job(scheduler)
        except Exception as e:
            logger.critical("Error when initializing %s - %s", module, e)

    scheduler.start()
