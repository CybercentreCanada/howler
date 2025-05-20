import json
import logging
import logging.handlers
import os
import re
from traceback import format_exception
from typing import TYPE_CHECKING, Optional, Union

from flask import request
from typing_extensions import override  # type: ignore

from howler.common import loader
from howler.common.logging.format import (
    HWL_DATE_FORMAT,
    HWL_JSON_FORMAT,
    HWL_LOG_FORMAT,
    HWL_SYSLOG_FORMAT,
)

if TYPE_CHECKING:
    from howler.odm.models.config import Config

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "DISABLED": 60,
}

DEBUG = False


class JsonFormatter(logging.Formatter):
    """logging Formatter to output in JSON"""

    @override
    def formatMessage(self, record):
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info)
            record.exc_info = None

        if record.exc_text:
            record.message += "\n" + record.exc_text
            record.exc_text = None

        record.message = json.dumps(record.message)
        return self._style.format(record)

    @override
    def formatException(self, exc_info):
        return "".join(format_exception(*exc_info))


def init_log_to_file(logger: logging.Logger, log_level: int, name: str, config: "Config"):
    """Initialize file-based logging"""
    if not os.path.isdir(config.logging.log_directory):
        logger.warning(
            "Log directory does not exist. Will try to create %s",
            config.logging.log_directory,
        )
        os.makedirs(config.logging.log_directory)

    if log_level <= logging.DEBUG:
        dbg_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(config.logging.log_directory, f"{name}.dbg"),
            maxBytes=10485760,
            backupCount=5,
        )
        dbg_file_handler.setLevel(logging.DEBUG)
        if config.logging.log_as_json:
            dbg_file_handler.setFormatter(JsonFormatter(HWL_JSON_FORMAT))
        else:
            dbg_file_handler.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
        logger.addHandler(dbg_file_handler)

    if log_level <= logging.INFO:
        op_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(config.logging.log_directory, f"{name}.log"),
            maxBytes=10485760,
            backupCount=5,
        )
        op_file_handler.setLevel(logging.INFO)
        if config.logging.log_as_json:
            op_file_handler.setFormatter(JsonFormatter(HWL_JSON_FORMAT))
        else:
            op_file_handler.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
        logger.addHandler(op_file_handler)

    if log_level <= logging.ERROR:
        err_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(config.logging.log_directory, f"{name}.err"),
            maxBytes=10485760,
            backupCount=5,
        )
        err_file_handler.setLevel(logging.ERROR)
        if config.logging.log_as_json:
            err_file_handler.setFormatter(JsonFormatter(HWL_JSON_FORMAT))
        else:
            err_file_handler.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
        err_file_handler.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
        logger.addHandler(err_file_handler)


def init_logging(name: str, log_level: Optional[int] = None):
    """Initialize the logger"""
    from howler.config import config

    logger = logging.getLogger(loader.APP_NAME)

    # Test if we've initialized the log handler already.
    if len(logger.handlers) != 0:
        return logger.getChild(name)

    if name.startswith(f"{loader.APP_NAME}."):
        name = name[len(loader.APP_NAME) + 1 :]

    config.logging.log_to_console = config.logging.log_to_console or config.ui.debug

    if log_level is None:
        log_level = LOG_LEVEL_MAP[config.logging.log_level]

    logging.root.setLevel(logging.CRITICAL)
    logger.setLevel(log_level)

    if config.logging.log_level == "DISABLED":
        # While log_level is set to disable, we will not create any handlers
        return logger.getChild(name)

    if config.logging.log_to_file:
        init_log_to_file(logger, log_level, name, config)

    if config.logging.log_to_console:
        console = logging.StreamHandler()
        if config.logging.log_as_json:
            console.setFormatter(JsonFormatter(HWL_JSON_FORMAT))
        else:
            console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
        logger.addHandler(console)

    if config.logging.log_to_syslog and config.logging.syslog_host and config.logging.syslog_port:
        syslog_handler = logging.handlers.SysLogHandler(
            address=(config.logging.syslog_host, config.logging.syslog_port)
        )
        syslog_handler.formatter = logging.Formatter(HWL_SYSLOG_FORMAT)
        logger.addHandler(syslog_handler)

    logger.debug("Logger ready!")
    return logger.getChild(name)


def get_logger(name: str = "default") -> logging.Logger:
    """Get a logger with a useful name given a filename"""
    name = re.sub(r".+(howler|test)/", "", name).replace("/", ".").replace(".__init__", "").replace(".py", "")
    name = re.sub(r"^api\.?", "", name)
    logger = init_logging("api")
    if name:
        logger = logger.getChild(name)
    return logger


def get_traceback_info(tb):
    """Prase the traceback information for a given traceback"""
    tb_list = []
    tb_id = 0
    last_ui = None
    while tb is not None:
        f = tb.tb_frame
        line_no = tb.tb_lineno
        tb_list.append((f, line_no))
        tb = tb.tb_next
        if "/ui/" in f.f_code.co_filename:
            last_ui = tb_id
        tb_id += 1

    if last_ui is not None:
        tb_frame, line = tb_list[last_ui]
        user = tb_frame.f_locals.get("kwargs", {}).get("user", None)

        if not user:
            temp = tb_frame.f_locals.get("_", {})
            if isinstance(temp, dict):
                user = temp.get("user", None)

        if not user:
            user = tb_frame.f_locals.get("user", None)

        if not user:
            user = tb_frame.f_locals.get("impersonator", None)

        if user:
            return user, tb_frame.f_code.co_filename, tb_frame.f_code.co_name, line

        return None

    return None


def __dumb_log(log, msg, is_exception=False):
    """Dumb logger for use with log_with_traceback"""
    args: Union[str, bytes] = request.query_string
    if isinstance(args, bytes):
        args = args.decode()

    if args:
        args = f"?{args}"

    message = f"{msg} - {request.path}{args}"
    if is_exception:
        log.exception(message)
    else:
        log.warning(message)


def log_with_traceback(traceback, msg, is_exception=False, audit=False):
    """Log a message along with the stacktrace"""
    log = get_logger("traceback") if not audit else logging.getLogger("howler.api.audit")

    tb_info = get_traceback_info(traceback)
    if tb_info:
        tb_user, tb_file, tb_function, tb_line_no = tb_info
        args: Optional[Union[str, bytes]] = request.query_string
        if args:
            args = f"?{args if isinstance(args, str) else args.decode()}"
        else:
            args = ""

        try:
            message = (
                f'{tb_user["uname"]} [{tb_user["classification"]}] :: {msg} - {tb_file}:{tb_function}:{tb_line_no}'
                f'[{os.environ.get("HOWLER_VERSION", "0.0.0.dev0")}] ({request.path}{args})'
            )
            if is_exception:
                log.exception(message)
            else:
                log.warning(message)
        except Exception:
            __dumb_log(log, msg, is_exception=is_exception)
    else:
        __dumb_log(log, msg, is_exception=is_exception)
