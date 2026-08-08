from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from energy_engine import SettlementPeriod


def test_end_is_thirty_minutes_after_start():
    period = SettlementPeriod(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))
    assert period.end == period.start + timedelta(minutes=30)


@pytest.mark.parametrize("minute", [1, 15, 29, 45])
def test_rejects_start_not_aligned_to_half_hour(minute):
    with pytest.raises(ValueError):
        SettlementPeriod(datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc))


def test_rejects_naive_datetime():
    with pytest.raises(ValueError):
        SettlementPeriod(datetime(2026, 1, 1, 0, 0))
