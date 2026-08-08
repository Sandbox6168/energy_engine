"""Shared HA recorder-statistics reading, used by both the Data Source and the
Tariff Provider (ADR-0001 / ADR-0002: both read only from HA's own history, never
an external API).

NOTE: written against the documented `statistics_during_period` API but not yet
exercised against a running Home Assistant instance - verify against a live HA
before relying on this in production.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from enum import Enum

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant

from .const import SHORT_TERM_STATS_RETENTION_DAYS
from .core import SettlementPeriod

_LOGGER = logging.getLogger(__name__)


class StatKind(Enum):
    """How to reduce a bucket of statistics rows down to one Settlement Period value."""

    CUMULATIVE = "cumulative"  # energy sensors (total_increasing): delta between sums
    INSTANTANEOUS = "instantaneous"  # rate / standing-charge sensors: mean of the bucket


class MissingStatisticsError(Exception):
    """Raised when a Settlement Period has no recorded data for an entity at all.

    Per CONTEXT.md: a precision caveat is only for genuinely coarser data (see
    `degraded` below) - a gap with no data at all must fail the run, not degrade it.
    """


async def async_fetch_settlement_values(
    hass: HomeAssistant,
    entity_id: str,
    start: datetime,
    end: datetime,
    kind: StatKind,
) -> tuple[dict[SettlementPeriod, float], bool]:
    """Fetch `entity_id`'s recorder history for [start, end), bucketed into Settlement Periods.

    Returns (values_by_period, degraded). `degraded` is True if any period had to fall
    back to hourly long-term statistics rather than true half-hourly short-term ones.
    """
    now = datetime.now(tz=UTC)
    cutoff = max(start, min(end, now - timedelta(days=SHORT_TERM_STATS_RETENTION_DAYS)))

    old_rows = await _query(hass, entity_id, start, cutoff, "hour") if cutoff > start else []
    recent_rows = await _query(hass, entity_id, cutoff, end, "5minute") if end > cutoff else []
    _LOGGER.debug(
        "%s: fetched %d hourly row(s) for %s..%s and %d 5-minute row(s) for %s..%s "
        "(kind=%s); hourly range=%s recent range=%s",
        entity_id, len(old_rows), start.isoformat(), cutoff.isoformat(),
        len(recent_rows), cutoff.isoformat(), end.isoformat(), kind.value,
        [_row_start(r).isoformat() for r in old_rows[:3]] + (["..."] if len(old_rows) > 3 else []),
        [_row_start(r).isoformat() for r in recent_rows[:3]]
        + (["..."] if len(recent_rows) > 3 else []),
    )

    values: dict[SettlementPeriod, float] = {}
    degraded = False

    period_start = start
    while period_start < end:
        period = SettlementPeriod(period_start)
        if period_start < cutoff:
            value = _reduce(old_rows, period_start, timedelta(hours=1), kind)
            if value is not None:
                degraded = True
        else:
            value = _reduce(recent_rows, period_start, timedelta(minutes=30), kind)

        if value is None:
            bucket_rows = old_rows if period_start < cutoff else recent_rows
            _LOGGER.warning(
                "No recorder data for %s covering the Settlement Period starting %s; "
                "nearest fetched row(s): %s",
                entity_id, period_start.isoformat(),
                [(r.get("start"), r.get("mean"), r.get("sum")) for r in bucket_rows[:5]],
            )
            raise MissingStatisticsError(
                f"No recorder data for {entity_id} covering the Settlement Period "
                f"starting {period_start.isoformat()}"
            )

        values[period] = value
        period_start += timedelta(minutes=30)

    return values, degraded


async def _query(
    hass: HomeAssistant, entity_id: str, start: datetime, end: datetime, period: str
) -> list[dict]:
    recorder = get_instance(hass)
    stats = await recorder.async_add_executor_job(
        statistics_during_period,
        hass,
        start,
        end,
        {entity_id},
        period,
        None,
        {"sum", "mean"},
    )
    return stats.get(entity_id, [])


def _reduce(
    rows: list[dict], bucket_start: datetime, bucket_span: timedelta, kind: StatKind
) -> float | None:
    bucket_end = bucket_start + bucket_span
    in_bucket = [row for row in rows if bucket_start <= _row_start(row) < bucket_end]
    if not in_bucket:
        return None

    if kind is StatKind.INSTANTANEOUS:
        means = [row["mean"] for row in in_bucket if row.get("mean") is not None]
        return sum(means) / len(means) if means else None

    sums = [row["sum"] for row in in_bucket if row.get("sum") is not None]
    if len(sums) < 2:
        return None
    return sums[-1] - sums[0]


def _row_start(row: dict) -> datetime:
    start = row["start"]
    return start if isinstance(start, datetime) else datetime.fromtimestamp(start, tz=UTC)
