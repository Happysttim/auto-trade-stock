from __future__ import annotations

from openai import OpenAI

from ..config import Settings
from ..prompts import TRADE_SYSTEM_PROMPT, build_user_prompt
from ..schemas import AITradePlan, AccountSnapshot, MarketWatchSnapshot, NewsArticle


class OpenAIAnalysisService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key or None,
            timeout=settings.openai_timeout_seconds,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def analyze(
        self,
        *,
        now_iso: str,
        articles: list[NewsArticle],
        watchlist: list[MarketWatchSnapshot],
        account: AccountSnapshot,
        previous_summary: str | None,
        operation_window: bool,
    ) -> AITradePlan:
        user_prompt = build_user_prompt(
            now_iso=now_iso,
            articles=articles,
            watchlist=watchlist,
            account=account,
            previous_summary=previous_summary,
            operation_window=operation_window,
            min_hold_days=self.settings.min_hold_days,
            max_hold_days=self.settings.max_hold_days,
            max_total_exposure_ratio=self.settings.account_max_exposure_ratio,
            minimum_meaningful_account_impact_ratio=self.settings.min_account_impact_ratio,
        )

        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": TRADE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            text_format=AITradePlan,
        )

        if response.output_parsed is None:
            raise RuntimeError("OpenAI returned no structured response.")
        return response.output_parsed
