from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class NewsSourceConfig:
    name: str
    url: str
    region: str
    topic: str


@dataclass(frozen=True, slots=True)
class Settings:
    backend_root: Path
    db_path: Path
    openai_api_key: str
    openai_model: str
    openai_timeout_seconds: int
    app_timezone: str
    operation_start_hour: int
    operation_end_hour: int
    operation_days: tuple[int, ...]
    service_loop_seconds: int
    news_scan_interval_minutes: int
    news_lookback_minutes: int
    news_max_articles: int
    watchlist_symbols: tuple[str, ...]
    watchlist_name_map: dict[str, str]
    max_volume_spike_ratio: float
    account_max_exposure_ratio: float
    min_account_impact_ratio: float
    min_hold_days: int
    max_hold_days: int
    flask_host: str
    flask_port: int
    flask_debug: bool
    request_timeout_seconds: int
    market_timezone: str
    market_open: str
    market_close: str
    market_trading_days: tuple[int, ...]
    kiwoom_app_key: str
    kiwoom_secret_key: str
    kiwoom_base_url: str
    kiwoom_mock_base_url: str
    kiwoom_use_mock: bool
    kiwoom_account_no: str
    kiwoom_exchange_code: str
    kiwoom_order_type_code: str
    kiwoom_request_timeout_seconds: int
    kiwoom_fallback_cash_balance: float
    kiwoom_accounts_body: dict[str, Any]
    kiwoom_cash_body: dict[str, Any]
    kiwoom_holdings_body: dict[str, Any]
    kiwoom_order_body: dict[str, Any]
    news_sources: tuple[NewsSourceConfig, ...]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw is not None else default


def _csv_env(name: str, default: Iterable[str]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return tuple(default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _int_csv_env(name: str, default: Iterable[int]) -> tuple[int, ...]:
    raw = os.getenv(name)
    if not raw:
        return tuple(default)
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())


def _path_env(name: str, default_relative: str, backend_root: Path) -> Path:
    raw = os.getenv(name, default_relative)
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return backend_root / candidate


def _json_env(name: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = os.getenv(name)
    if not raw:
        return dict(default or {})
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must be a JSON object.")
    return parsed


def _google_news_rss(query: str, *, hl: str, gl: str, ceid: str) -> str:
    return (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    )


def _normalize_symbol_key(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".KS") or normalized.endswith(".KQ"):
        normalized = normalized.split(".", 1)[0]
    return normalized


def _normalize_name_map(raw_map: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_map.items():
        key_text = _normalize_symbol_key(str(key))
        value_text = str(value).strip()
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized


def _default_news_sources() -> tuple[NewsSourceConfig, ...]:
    return (
        NewsSourceConfig(
            name="Reuters Markets",
            url=_google_news_rss(
                "when:1h (stock market OR central bank OR geopolitics) site:reuters.com",
                hl="en-US",
                gl="US",
                ceid="US:en",
            ),
            region="global",
            topic="markets",
        ),
        NewsSourceConfig(
            name="AP Business",
            url=_google_news_rss(
                "when:1h (stock market OR geopolitics OR economy) site:apnews.com",
                hl="en-US",
                gl="US",
                ceid="US:en",
            ),
            region="global",
            topic="world",
        ),
        NewsSourceConfig(
            name="CNBC Markets",
            url=_google_news_rss(
                "when:1h (stocks OR market OR treasury yields) site:cnbc.com",
                hl="en-US",
                gl="US",
                ceid="US:en",
            ),
            region="global",
            topic="markets",
        ),
        NewsSourceConfig(
            name="Yonhap News",
            url=_google_news_rss(
                "when:1h (stock OR economy OR geopolitics OR kospi) site:yna.co.kr",
                hl="ko",
                gl="KR",
                ceid="KR:ko",
            ),
            region="korea",
            topic="markets",
        ),
        NewsSourceConfig(
            name="Maeil Business",
            url=_google_news_rss(
                "when:1h (stock OR economy OR market OR kospi) site:mk.co.kr",
                hl="ko",
                gl="KR",
                ceid="KR:ko",
            ),
            region="korea",
            topic="economy",
        ),
    )


def _default_watchlist_name_map() -> dict[str, str]:
    return {
        "005930": "삼성전자",
        "000660": "SK하이닉스",
        "035420": "NAVER",
        "051910": "LG화학",
        "068270": "셀트리온",
        "105560": "KB금융",
        "207940": "삼성바이오로직스",
        "323410": "카카오뱅크",
    }


def load_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    load_dotenv(backend_root / ".env")

    settings = Settings(
        backend_root=backend_root,
        db_path=_path_env("DB_PATH", "data/auto_trade_stock.db", backend_root),
        openai_api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        openai_timeout_seconds=_int_env("OPENAI_TIMEOUT_SECONDS", 45),
        app_timezone=os.getenv("APP_TIMEZONE", "Asia/Seoul"),
        operation_start_hour=_int_env("OPERATION_START_HOUR", 7),
        operation_end_hour=_int_env("OPERATION_END_HOUR", 18),
        operation_days=_int_csv_env("OPERATION_DAYS", (0, 1, 2, 3, 4)),
        service_loop_seconds=_int_env("SERVICE_LOOP_SECONDS", 60),
        news_scan_interval_minutes=_int_env("NEWS_SCAN_INTERVAL_MINUTES", 120),
        news_lookback_minutes=_int_env("NEWS_LOOKBACK_MINUTES", 60),
        news_max_articles=_int_env("NEWS_MAX_ARTICLES", 8),
        watchlist_symbols=_csv_env(
            "WATCHLIST_SYMBOLS",
            (
                "005930.KS",
                "000660.KS",
                "035420.KS",
                "051910.KS",
                "068270.KS",
                "105560.KS",
                "207940.KS",
                "323410.KS",
            ),
        ),
        watchlist_name_map=_normalize_name_map(
            _json_env("WATCHLIST_NAME_MAP_JSON", _default_watchlist_name_map())
        ),
        max_volume_spike_ratio=_float_env("MAX_VOLUME_SPIKE_RATIO", 4.0),
        account_max_exposure_ratio=_float_env("ACCOUNT_MAX_EXPOSURE_RATIO", 0.75),
        min_account_impact_ratio=_float_env("MIN_ACCOUNT_IMPACT_RATIO", 0.10),
        min_hold_days=_int_env("MIN_HOLD_DAYS", 1),
        max_hold_days=_int_env("MAX_HOLD_DAYS", 7),
        flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
        flask_port=_int_env("FLASK_PORT", 5000),
        flask_debug=_bool_env("FLASK_DEBUG", True),
        request_timeout_seconds=_int_env("REQUEST_TIMEOUT_SECONDS", 20),
        market_timezone=os.getenv("MARKET_TIMEZONE", "Asia/Seoul"),
        market_open=os.getenv("MARKET_OPEN", "09:00"),
        market_close=os.getenv("MARKET_CLOSE", "15:30"),
        market_trading_days=_int_csv_env("MARKET_TRADING_DAYS", (0, 1, 2, 3, 4)),
        kiwoom_app_key=os.getenv("KIWOOM_APP_KEY", "").strip(),
        kiwoom_secret_key=os.getenv("KIWOOM_SECRET_KEY", "").strip(),
        kiwoom_base_url=os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/"),
        kiwoom_mock_base_url=os.getenv("KIWOOM_MOCK_BASE_URL", "https://mockapi.kiwoom.com").rstrip("/"),
        kiwoom_use_mock=_bool_env("KIWOOM_USE_MOCK", True),
        kiwoom_account_no=os.getenv("KIWOOM_ACCOUNT_NO", "").strip(),
        kiwoom_exchange_code=os.getenv("KIWOOM_EXCHANGE_CODE", "KRX"),
        kiwoom_order_type_code=os.getenv("KIWOOM_ORDER_TYPE_CODE", "3"),
        kiwoom_request_timeout_seconds=_int_env("KIWOOM_REQUEST_TIMEOUT_SECONDS", 20),
        kiwoom_fallback_cash_balance=_float_env("KIWOOM_FALLBACK_CASH_BALANCE", 0.0),
        kiwoom_accounts_body=_json_env("KIWOOM_ACCOUNTS_BODY_JSON", {}),
        kiwoom_cash_body=_json_env("KIWOOM_CASH_BODY_JSON", {"acct_no": "{account_no}"}),
        kiwoom_holdings_body=_json_env("KIWOOM_HOLDINGS_BODY_JSON", {"acct_no": "{account_no}"}),
        kiwoom_order_body=_json_env("KIWOOM_ORDER_BODY_JSON", {"acct_no": "{account_no}"}),
        news_sources=_default_news_sources(),
    )

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
