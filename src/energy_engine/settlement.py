from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class SettlementPeriod:
    """A fixed 30-minute UK billing window aligned to :00/:30."""

    start: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError("SettlementPeriod.start must be timezone-aware")
        if self.start.minute not in (0, 30) or self.start.second or self.start.microsecond:
            raise ValueError("SettlementPeriod.start must align to :00 or :30")

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=30)
