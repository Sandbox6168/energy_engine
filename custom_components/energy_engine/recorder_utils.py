"""Shared HA recorder-statistics reading, used by both the Data Source and the
Tariff Provider (ADR-0001 / ADR-0002: both read only from HA's own history, never
an external API).

NOTE: written against the documented `statistics_during_period` API but not yet
exercised against a running Home Assistant instance - verify against a live HA
before relying on this in production.
"""

from __future__ import annotations

import functools
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.statistics import (
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant

from .const import SHORT_TERM_STATS_RETENTION_DAYS
from .core import SettlementPeriod


class StatKind(Enum):
    """How to reduce a bucket of statistics rows down to one Settlement Period value,
    or (HISTORY) how to resolve a per-day value from plain state history instead."""

    CUMULATIVE = "cumulative"  # energy sensors (total_increasing): delta between sums
    INSTANTANEOUS = "instantaneous"  # rate sensors: mean of the bucket
    HISTORY = "history"  # rarely-changing values (standing charge): state-at-day-start


class MissingStatisticsError(Exception):
    """Raised when a Settlement Period has no recorded data for an entity at all.

    Per CONTEXT.md: a precision caveat is only for genuinely coarser data (see
    `degraded` below) - a gap with no data at all must fail the run, not degrade it.
    """


class MissingHistoryError(Exception):
    """Raised when an entity has no recorded state history at all (see
    `async_fetch_daily_value_from_history`) - the history equivalent of
    `MissingStatisticsError`, for values resolved from plain state history."""


def clamp_to_completed_period(end_dt: datetime) -> datetime:
    """Clamp `end_dt` so a request never reaches into the still-in-progress Settlement
    Period.

    Callers build `end_dt` from a calendar date (e.g. "today" -> tomorrow midnight),
    which reaches past the present moment for any period that hasn't finished yet.
    That period can never have data, so left unclamped every "today"/"this week" run
    would fail with `MissingStatisticsError` until the day is over.
    """
    now = datetime.now(tz=UTC)
    if end_dt <= now:
        return end_dt
    return now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)


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
            raise MissingStatisticsError(
                f"No recorder data for {entity_id} covering the Settlement Period "
                f"starting {period_start.isoformat()}"
            )

        values[period] = value
        period_start += timedelta(minutes=30)

    return values, degraded


async def async_fetch_daily_value_from_history(
    hass: HomeAssistant, entity_id: str, start: date, end: date
) -> tuple[dict[date, Decimal], bool]:
    """Resolve `entity_id`'s plain state history to one value per day in [start, end).

    For values that only change rarely (e.g. a standing charge, which only changes
    when the tariff changes) statistics are the wrong tool - they need bucket-mean/sum
    reduction, this needs "what was the state at the start of this day". Uses HA's raw
    state history instead, which every entity has regardless of `state_class`.

    Returns (values_by_day, degraded). `degraded` is True if a day's state had to fall
    back to the earliest known state because history doesn't reach back that far -
    per CONTEXT.md, a day with genuinely no history at all raises `MissingHistoryError`
    instead of silently degrading.
    """
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.min, tzinfo=UTC) + timedelta(days=1)

    job = functools.partial(
        history.state_changes_during_period,
        hass,
        start_dt,
        end_dt,
        entity_id,
        include_start_time_state=True,
        no_attributes=True,
    )
    raw = await get_instance(hass).async_add_executor_job(job)

    numeric_states: list[tuple[datetime, Decimal]] = []
    for state in raw.get(entity_id, []):
        try:
            numeric_states.append((state.last_changed, Decimal(state.state)))
        except (InvalidOperation, TypeError):
            continue

    if not numeric_states:
        raise MissingHistoryError(f"No recorded state history at all for {entity_id}")

    values: dict[date, Decimal] = {}
    degraded = False

    day = start
    while day < end:
        day_start = datetime.combine(day, time.min, tzinfo=UTC)
        at_or_before = [value for changed, value in numeric_states if changed <= day_start]
        if at_or_before:
            values[day] = at_or_before[-1]
        else:
            values[day] = numeric_states[0][1]
            degraded = True
        day += timedelta(days=1)

    return values, degraded


async def async_entity_supports_statistics(
    hass: HomeAssistant, entity_id: str, kind: StatKind
) -> bool:
    """Whether `entity_id` has any long-term statistics of the kind we'd need at all.

    Distinct from a data *gap* (see `MissingStatisticsError`): an entity can be perfectly
    available and still never have been tracked for statistics - e.g. a sensor with no
    `state_class`. `_reduce`/`async_fetch_settlement_values` can't tell those two failure
    modes apart on their own, since a bucket with zero rows looks the same either way.
    """
    recorder = get_instance(hass)
    metadata = await recorder.async_add_executor_job(list_statistic_ids, hass, {entity_id})
    if not metadata:
        return False

    info = metadata[0]
    return bool(info["has_sum"]) if kind is StatKind.CUMULATIVE else bool(info["has_mean"])


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
