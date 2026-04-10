from __future__ import annotations

import logging
import sys
from datetime import datetime

_ANSI = {
    "reset": "\033[0m",
    "blue": "\033[94m",
    "orange": "\033[38;5;214m",
    "white": "\033[97m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "magenta": "\033[95m",
}


def _paint(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{_ANSI.get(color, '')}{text}{_ANSI['reset']}"


def _level_tag(levelno: int) -> str:
    if levelno >= logging.ERROR:
        return _paint("<ERR>", "red")
    if levelno >= logging.WARNING:
        return _paint("<WRN>", "yellow")
    if levelno <= logging.DEBUG:
        return _paint("<DBG>", "magenta")
    return _paint("<INF>", "blue")


class TimelineFormatter(logging.Formatter):
    """Compact timeline logging: HH:MM:SS <TAG> message"""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        msg = record.getMessage()
        return f"{ts} {_level_tag(record.levelno)} {msg}"


def setup_logging(debug: bool = False) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.setFormatter(TimelineFormatter())
    root.addHandler(handler)


def scrape_log(logger: logging.Logger, event: str, *, site: str | None = None, extra: str = "", level: int = logging.INFO) -> None:
    evt = _paint(event, "white")
    who = _paint(site, "orange") if site else ""
    message = f"{evt}" + (f" : {who}" if site else "")
    if extra:
        message = f"{message} | {extra}"
    logger.log(level, message)

