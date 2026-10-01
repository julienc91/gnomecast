import logging
import os
import sys
import threading
from typing import TextIO

from typing_extensions import override

_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"

_RESET = "\033[0m"
_DIM = "\033[2m"
_LEVEL_COLORS = {
    logging.DEBUG: _DIM,
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}

# Chatty third-party loggers: errors only, or warnings in verbose mode
_QUIET_LOGGERS = ("asyncio", "paste", "pychromecast", "zeroconf")

logger = logging.getLogger("gnomecast")


class _Formatter(logging.Formatter):
    def __init__(self, color: bool):
        super().__init__(_FORMAT, _DATE_FORMAT)
        self.color = color

    @override
    def formatTime(self, record, datefmt=None):
        asctime = super().formatTime(record, datefmt)
        return _DIM + asctime if self.color else asctime

    @override
    def format(self, record):
        record = logging.makeLogRecord(record.__dict__)
        record.name = record.name.removeprefix("gnomecast.")
        if self.color:
            # Reset closes the dimmed timestamp
            color = _LEVEL_COLORS.get(record.levelno, "")
            record.levelname = f"{_RESET}{color}{record.levelname:<7}{_RESET}"
        return super().format(record)


def _use_color(stream: TextIO) -> bool:
    return stream.isatty() and "NO_COLOR" not in os.environ


def setup_logging(verbose: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Formatter(color=_use_color(sys.stderr)))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING if verbose else logging.ERROR)

    def excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    def thread_excepthook(args):
        if args.exc_type is SystemExit:
            return
        logger.error(
            "Uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
