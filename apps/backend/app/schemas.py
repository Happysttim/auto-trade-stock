from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class NewsArticle:
    article_id: str
    title: str
    source_name: str
    url: str
    published_at: datetime
    summary: str
    region: str
    topic: str

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "source_name": self.source_name,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "summary": self.summary,
            "region": self.region,
            "topic": self.topic,
        }


@dataclass(slots=True)
class MarketWatchSnapshot:
    symbol: str
    company_name: str
    last_close: float
    recent_volume: int
    average_volume_20d: float
    volume_ratio: float
    suspicious_volume: bool
    price_change_pct: float

    def to_prompt_dict(self) -> dict[str, str | float | int | bool]:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "last_close": round(self.last_close, 4),
            "recent_volume": self.recent_volume,
            "average_volume_20d": round(self.average_volume_20d, 2),
            "volume_ratio": round(self.volume_ratio, 4),
            "suspicious_volume": self.suspicious_volume,
            "price_change_pct": round(self.price_change_pct, 4),
        }


@dataclass(slots=True)
class Holding:
    symbol: str
    company_name: str
    quantity: int
    market_value: float
    account_no: str | None = None
    available_quantity: int = 0
    average_price: float = 0.0
    current_price: float = 0.0
    pnl: float | None = None


@dataclass(slots=True)
class AccountSnapshot:
    cash_balance: float
    holdings: list[Holding] = field(default_factory=list)
    account_no: str | None = None

    @property
    def holdings_value(self) -> float:
        return sum(holding.market_value for holding in self.holdings)

    @property
    def total_equity(self) -> float:
        return self.cash_balance + self.holdings_value

    def holding_for_symbol(self, symbol: str) -> Holding | None:
        normalized = symbol.upper()
        for holding in self.holdings:
            if holding.symbol.upper() == normalized:
                return holding
        return None


@dataclass(slots=True)
class NewsSelectionResult:
    articles: list[NewsArticle]
    signature: str
    mode: str
    skip_reason: str | None = None


@dataclass(slots=True)
class BrokerOrderResult:
    success: bool
    broker_order_id: str | None
    message: str
    raw_payload: dict[str, object] | None = None


class TradeRecommendationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    company_name: str
    keyword: str
    score: int = Field(ge=0, le=100)
    signal_type: Literal["buy", "sell", "hold"]
    allocation_ratio: float = Field(ge=0.0, le=0.75)
    hold_days: int = Field(ge=1, le=7)
    recent_volume: int = Field(ge=0)
    volume_ratio: float = Field(ge=0.0)
    suspicious_volume: bool = False
    recorded_date: str
    rationale: str
    source_article_ids: list[str] = Field(default_factory=list)


class AITradePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_sentiment_summary: str
    context_changed: bool = True
    skip_reason: str | None = None
    recommendations: list[TradeRecommendationModel] = Field(default_factory=list, max_length=3)
