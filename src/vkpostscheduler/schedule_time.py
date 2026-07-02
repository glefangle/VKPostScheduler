"""Canonical time handling; every string conversion goes through the parsers here."""

import datetime
import re

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
# a queued job is keyd by its day and time of day
PUBLISH_FORMAT = f"{DATE_FORMAT} {TIME_FORMAT}"

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_time(text: str) -> datetime.time:
    """Parse a strict HH:MM string; anything else is a ValueError."""
    match = _TIME_RE.match(text.strip())
    if not match:
        raise ValueError(f"Bad time '{text}', expected HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"Bad time '{text}', expected HH:MM")
    return datetime.time(hour, minute)


def format_time(value: datetime.time) -> str:
    """The canonical on-disk/display form ``HH:MM``."""
    return f"{value.hour:02d}:{value.minute:02d}"


def job_key(day: datetime.date, value: datetime.time) -> str:
    """The string key one queued job hangs on: ``YYYY-MM-DD HH:MM``."""
    return f"{day.strftime(DATE_FORMAT)} {format_time(value)}"


def parse_publish_time(key: str) -> datetime.datetime:
    """Parse a job key back into a naive datetime."""
    return datetime.datetime.strptime(key, PUBLISH_FORMAT)
