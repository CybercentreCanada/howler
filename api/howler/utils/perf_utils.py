import cProfile
import math
import pstats
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from howler.common.logging import get_logger

logger = get_logger(__file__)


@contextmanager
def profile(sort_by: str = "tottime", limit: int = 20, prefix: str | None = None) -> Generator:
    """Profile the code inside the context and print the top results."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield
    finally:
        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats(sort_by)
        stats.print_stats(limit)
        stats_file = (
            Path(tempfile.mkdtemp()) / f"{prefix or ''}{'_' if prefix else ''}{math.floor(time.monotonic())}.pstats"
        )
        stats.dump_stats(stats_file)
        logger.info(f"Saved to {stats_file}")
