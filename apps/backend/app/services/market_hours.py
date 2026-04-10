from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from ..config import Settings


def _parse_clock(raw: str) -> time:
    hour, minute = raw.split(":")
    return time(hour=int(hour), minute=int(minute))


@dataclass(slots=True)
class MarketClock:
    settings: Settings
    app_tz: ZoneInfo = field(init=False)
    market_tz: ZoneInfo = field(init=False)
    market_open_time: time = field(init=False)
    market_close_time: time = field(init=False)

    def __post_init__(self) -> None:
        self.app_tz = ZoneInfo(self.settings.app_timezone)
        self.market_tz = ZoneInfo(self.settings.market_timezone)
        self.market_open_time = _parse_clock(self.settings.market_open)
        self.market_close_time = _parse_clock(self.settings.market_close)

    def now(self) -> datetime:
        return datetime.now(self.app_tz)

    def is_operating_window(self, moment: datetime | None = None) -> bool:
        current = moment.astimezone(self.app_tz) if moment else self.now()
        if current.weekday() not in self.settings.operation_days:
            return False
        return self.settings.operation_start_hour <= current.hour < self.settings.operation_end_hour

    def is_market_open(self, moment: datetime | None = None) -> bool:
        current = moment.astimezone(self.market_tz) if moment else datetime.now(self.market_tz)
        if current.weekday() not in self.settings.market_trading_days:
            return False
        current_time = current.time()
        return self.market_open_time <= current_time <= self.market_close_time


