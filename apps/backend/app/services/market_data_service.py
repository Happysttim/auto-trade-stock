from __future__ import annotations

from dataclasses import replace
from math import floor
import re
from datetime import datetime, timedelta, timezone

import yfinance as yf

from ..config import Settings
from ..schemas import MarketWatchSnapshot


class MarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[datetime, MarketWatchSnapshot]] = {}

    def _normalize_symbol_key(self, symbol: str) -> str:
        normalized = symbol.upper().strip()
        if normalized.endswith(".KS") or normalized.endswith(".KQ"):
            return normalized.split(".", 1)[0]
        return normalized

    def _normalize_compare_symbol(self, symbol: str) -> str:
        return self._normalize_symbol_key(symbol)

    def _ticker_symbol(self, symbol: str) -> str:
        normalized = symbol.upper()
        if re.fullmatch(r"\d{6}", normalized):
            return f"{normalized}.KS"
        return symbol

    def resolve_company_name(self, symbol: str) -> str:
        normalized_symbol = self._normalize_symbol_key(symbol)
        mapped_name = self.settings.watchlist_name_map.get(normalized_symbol)
        if mapped_name:
            return mapped_name
        return normalized_symbol or symbol

    def _apply_affordability(
        self,
        snapshot: MarketWatchSnapshot,
        *,
        buying_power: float | None,
        held_symbols: set[str],
    ) -> MarketWatchSnapshot:
        if buying_power is None or snapshot.last_close <= 0:
            max_affordable_quantity = 0
        else:
            max_affordable_quantity = max(0, floor(max(0.0, buying_power) / snapshot.last_close))

        normalized_symbol = self._normalize_symbol_key(snapshot.symbol)
        affordable = max_affordable_quantity >= 1 or normalized_symbol in held_symbols
        return replace(
            snapshot,
            max_affordable_quantity=max_affordable_quantity,
            affordable=affordable,
        )

    def build_watchlist(
        self,
        *,
        buying_power: float | None = None,
        held_symbols: set[str] | None = None,
        preferred_symbols: list[str] | None = None,
    ) -> list[MarketWatchSnapshot]:
        snapshots: list[MarketWatchSnapshot] = []
        now = datetime.now(timezone.utc)
        normalized_held_symbols = {self._normalize_symbol_key(symbol) for symbol in held_symbols or set()}
        candidate_symbols: list[str] = []
        seen_symbols: set[str] = set()

        for symbol in (preferred_symbols or []):
            normalized_symbol = self._normalize_symbol_key(symbol)
            if not normalized_symbol or normalized_symbol in seen_symbols:
                continue
            seen_symbols.add(normalized_symbol)
            candidate_symbols.append(normalized_symbol)

        for symbol in self.settings.watchlist_symbols:
            normalized_symbol = self._normalize_symbol_key(symbol)
            if not normalized_symbol or normalized_symbol in seen_symbols:
                continue
            seen_symbols.add(normalized_symbol)
            candidate_symbols.append(symbol)

        for symbol in candidate_symbols:
            cached = self._cache.get(symbol)
            if cached and now - cached[0] < timedelta(minutes=20):
                snapshot = self._apply_affordability(
                    cached[1],
                    buying_power=buying_power,
                    held_symbols=normalized_held_symbols,
                )
                if buying_power is not None and not snapshot.affordable:
                    continue
                snapshots.append(snapshot)
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
                    company_name=self.resolve_company_name(symbol),
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
            enriched_snapshot = self._apply_affordability(
                snapshot,
                buying_power=buying_power,
                held_symbols=normalized_held_symbols,
            )
            if buying_power is not None and not enriched_snapshot.affordable:
                continue
            snapshots.append(enriched_snapshot)

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
