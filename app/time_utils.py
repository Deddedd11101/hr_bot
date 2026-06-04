from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    # The current project stores UTC timestamps in timezone-naive DB columns.
    return datetime.now(UTC).replace(tzinfo=None)
