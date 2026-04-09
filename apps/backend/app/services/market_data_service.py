from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import yfinance as yf

from ..config import Settings
from ..schemas import MarketWatchSnapshot


class MarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[datetime, MarketWatchSnapshot]] = {}

    def _normalize_compare_symbol(self, symbol: str) -> str:
        normalized = symbol.upper()
        if normalized.endswith(".KS") or normalized.endswith(".KQ"):
            return normalized.split(".", 1)[0]
        return normalized

    def _ticker_symbol(self, symbol: str) -> str:
        normalized = symbol.upper()
        if re.fullmatch(r"\d{6}", normalized):
            return f"{normalized}.KS"
        return symbol

    def build_watchlist(self) -> list[MarketWatchSnapshot]:
        snapshots: list[MarketWatchSnapshot] = []
        now = datetime.now(timezone.utc)

        for symbol in self.settings.watchlist_symbols:
            cached = self._cache.get(symbol)
            if cached and now - cached[0] < timedelta(minutes=20):
                snapshots.append(cached[1])
                continue

            try:
                ticker = yf.Ticker(self._ticker_symbol(symbol))
                history = ticker.history(period="1mo", interval="1d", auto_adjust=False)
                if history.empty:
                    continue

                last_row = history.iloc[-1]
                close_price = float(last_row["Close"])
                recent_volume = int(last_row["Volume"])
                avg_volume = float(history["Volume"].tail(20).mean() or 0.0)
                previous_close = float(history["Close"].iloc[-2]) if len(history.index) > 1 else close_price
                price_change_pct = (
                    0.0 if previous_close == 0 else ((close_price - previous_close) / previous_close) * 100
                )
                volume_ratio = 0.0 if avg_volume <= 0 else recent_volume / avg_volume

                snapshot = MarketWatchSnapshot(
                    symbol=symbol,
                    company_name=symbol,
                    last_close=close_price,
                    recent_volume=recent_volume,
                    average_volume_20d=avg_volume,
                    volume_ratio=volume_ratio,
                    suspicious_volume=volume_ratio >= self.settings.max_volume_spike_ratio,
                    price_change_pct=price_change_pct,
                )
            except Exception:
                continue

            self._cache[symbol] = (now, snapshot)
            snapshots.append(snapshot)

        snapshots.sort(key=lambda item: item.recent_volume, reverse=True)
        return snapshots

    def get_latest_price(self, symbol: str) -> float:
        watchlist = self.build_watchlist()
        normalized_symbol = self._normalize_compare_symbol(symbol)
        for snapshot in watchlist:
            if self._normalize_compare_symbol(snapshot.symbol) == normalized_symbol:
                return snapshot.last_close

        ticker = yf.Ticker(self._ticker_symbol(symbol))
        history = ticker.history(period="5d", interval="1d", auto_adjust=False)
        if history.empty:
            return 0.0
        return float(history.iloc[-1]["Close"])
