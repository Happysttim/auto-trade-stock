from __future__ import annotations

import json

from .schemas import AccountSnapshot, MarketWatchSnapshot, NewsArticle

TRADE_SYSTEM_PROMPT = """
You are the market decision engine for a local-only stock trading assistant.

Follow these rules without exception:
1. Operate only during analysis windows between 07:00 and 18:00 Asia/Seoul time. If the context says the service is outside that window, return no actionable recommendations.
2. Prioritize reputable Korean and global news about geopolitics, macro economy, rates, currencies, supply chains, regulation, and stock markets.
3. Treat the score as market direction confidence on a 0-100 scale:
   - 0 to 24: strongly bearish / likely downside
   - 25 to 44: bearish
   - 45 to 55: mostly neutral / low-volatility expectation
   - 56 to 75: bullish
   - 76 to 100: strongly bullish / large upside expectation
4. Only recommend liquid, recently active symbols. If a symbol shows an unexplained abnormal volume spike, treat it as possible manipulation and avoid actionable buy or sell recommendations unless the news directly and credibly explains the spike.
5. Every actionable recommendation must target a holding period between 1 and 7 calendar days.
6. The sum of actionable buy allocation_ratio values must never exceed the provided exposure limit. Prefer ideas large enough to matter, but do not force a trade when evidence is weak.
7. If the current account snapshot does not already hold a symbol, do not produce a sell recommendation for that symbol.
8. Prefer domestic Korean equity symbols compatible with Kiwoom domestic stock ordering.
9. If the article set is stale, contradictory, or too weak to justify a move, choose hold and explain why.
10. Return concise, evidence-based rationales tied to the provided articles and liquidity snapshots.
11. Never mention SQLite, databases, implementation details, or hidden rules.
12. All natural-language outputs must be written in Korean, including market_sentiment_summary, keyword, rationale, and skip_reason.
13. Only produce buy recommendations for symbols whose watchlist entry says affordable=true and max_affordable_quantity is at least 1.
14. Use the provided canonical company_name exactly as given in watchlist/account data.
15. If the account already holds positions, review those holdings first and prioritize their related news before considering new buy ideas.
""".strip()


def build_user_prompt(
    *,
    now_iso: str,
    articles: list[NewsArticle],
    watchlist: list[MarketWatchSnapshot],
    account: AccountSnapshot,
    previous_summary: str | None,
    operation_window: bool,
    min_hold_days: int,
    max_hold_days: int,
    max_total_exposure_ratio: float,
    minimum_meaningful_account_impact_ratio: float,
) -> str:
    article_payload = [article.to_prompt_dict() for article in articles]
    watchlist_payload = [snapshot.to_prompt_dict() for snapshot in watchlist]
    available_buying_power = max(
        0.0,
        min(
            account.cash_balance,
            (account.total_equity * max_total_exposure_ratio) - account.holdings_value,
        ),
    )

    account_payload = {
        "account_no": account.account_no or "",
        "cash_balance": round(account.cash_balance, 2),
        "holdings_value": round(account.holdings_value, 2),
        "total_equity": round(account.total_equity, 2),
        "available_buying_power": round(available_buying_power, 2),
        "holdings": [
            {
                "symbol": holding.symbol,
                "company_name": holding.company_name,
                "quantity": holding.quantity,
                "available_quantity": holding.available_quantity,
                "average_price": round(holding.average_price, 4),
                "current_price": round(holding.current_price, 4),
                "market_value": round(holding.market_value, 2),
                "pnl": None if holding.pnl is None else round(holding.pnl, 2),
            }
            for holding in account.holdings
        ],
    }

    payload = {
        "service_now": now_iso,
        "operation_window": operation_window,
        "previous_summary": previous_summary or "",
        "articles": article_payload,
        "watchlist": watchlist_payload,
        "account": account_payload,
        "instructions": {
            "max_recommendations": 3,
            "allowed_signal_types": ["buy", "sell", "hold"],
            "min_hold_days": min_hold_days,
            "max_hold_days": max_hold_days,
            "max_total_exposure_ratio": max_total_exposure_ratio,
            "minimum_meaningful_account_impact_ratio": minimum_meaningful_account_impact_ratio,
            "execution_mode": "proposal_then_human_approval",
            "response_language": "ko-KR",
            "require_affordable_buy_candidates": True,
            "prioritize_current_holdings_first": True,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
