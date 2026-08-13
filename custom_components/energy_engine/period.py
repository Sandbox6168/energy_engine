"""Resolves a Lookback Period preset to a concrete date range ending now.

HA-only: the core engine and verification.py never see a Lookback Period, only the
[start, end] dates this produces. See CONTEXT.md's "Lookback Period" entry.
"""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta
from homeassistant.util import dt as dt_util

from .const import (
    PERIOD_MONTH,
    PERIOD_SIX_MONTHS,
    PERIOD_THREE_MONTHS,
    PERIOD_TODAY,
    PERIOD_WEEK,
    PERIOD_YEAR,
)

_DELTAS = {
    PERIOD_TODAY: relativedelta(days=0),
    PERIOD_WEEK: relativedelta(weeks=1),
    PERIOD_MONTH: relativedelta(months=1),
    PERIOD_THREE_MONTHS: relativedelta(months=3),
    PERIOD_SIX_MONTHS: relativedelta(months=6),
    PERIOD_YEAR: relativedelta(years=1),
}


def resolve_period(period: str) -> tuple[date, date]:
    """Resolve a Lookback Period preset to [start, end], both inclusive, ending today.

    Calendar-based (relativedelta), not fixed day-counts: "1 Year" means "same date
    last year," matching how the preset labels actually read.
    """
    end = dt_util.now().date()
    start = end - _DELTAS[period]
    return start, end
