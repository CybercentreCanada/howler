import logging

HWL_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"
HWL_DATE_FORMAT = "%y/%m/%d %H:%M:%S"

BASE_LOGGER = logging.getLogger("howler")
console = logging.StreamHandler()
console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
BASE_LOGGER.addHandler(console)


def get_logger(name: str) -> logging.Logger:
    "Create a logger instance with the given name"
    return BASE_LOGGER.getChild(name)
