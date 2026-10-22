from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime


def default_adaptation_end(first_workday: date) -> date:
    month_index = first_workday.year * 12 + first_workday.month - 1 + 3
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(first_workday.day, monthrange(year, month)[1]))


def utc_now() -> datetime:
    # The current project stores UTC timestamps in timezone-naive DB columns.
    return datetime.now(UTC).replace(tzinfo=None)
