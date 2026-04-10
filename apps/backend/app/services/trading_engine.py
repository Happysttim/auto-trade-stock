from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import floor
from typing import Any

from ..config import Settings
from ..database import Database
from ..schemas import AccountSnapshot, MarketWatchSnapshot
from .kiwoom_service import KiwoomBrokerService
from .market_data_service import MarketDataService
from .market_hours import MarketClock
from .news_service import NewsService
from .openai_service import OpenAIAnalysisService


class TradingEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: Database,
        clock: MarketClock,
        news_service: NewsService,
        market_data_service: MarketDataService,
        kiwoom_service: KiwoomBrokerService,
        openai_service: OpenAIAnalysisService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.clock = clock
        self.news_service = news_service
        self.market_data_service = market_data_service
        self.kiwoom_service = kiwoom_service
        self.openai_service = openai_service

    def _log(
        self,
        *,
        event_type: str,
        message: str,
        level: str = "info",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.save_system_log(
            event_type=event_type,
            level=level,
            message=message,
            metadata=metadata,
        )

    def _fallback_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            account_no=self.settings.kiwoom_account_no or None,
            cash_balance=self.settings.kiwoom_fallback_cash_balance,
            holdings=[],
        )

    def _normalize_orderable_symbol(self, symbol: str) -> str | None:
        normalized = symbol.strip().upper()
        if normalized.endswith(".KS") or normalized.endswith(".KQ"):
            normalized = normalized.split(".", 1)[0]
        if len(normalized) == 6 and normalized.isdigit():
            return normalized
        return None

    def _available_buying_power(self, account: AccountSnapshot) -> float:
        total_equity = account.total_equity or self.settings.kiwoom_fallback_cash_balance
        if total_equity <= 0:
            return 0.0
        max_total_trade_value = total_equity * self.settings.account_max_exposure_ratio
        exposure_room = max(0.0, max_total_trade_value - account.holdings_value)
        return max(0.0, min(account.cash_balance, exposure_room))

    def _resolve_company_name(self, symbol: str, *, account: AccountSnapshot | None = None) -> str:
        if account is not None:
            holding = account.holding_for_symbol(symbol)
            if holding is not None and holding.company_name:
                return holding.company_name
        return self.market_data_service.resolve_company_name(symbol)

    def _preferred_news_companies(self, account: AccountSnapshot) -> list[tuple[str, str]]:
        prioritized = sorted(account.holdings, key=lambda holding: holding.market_value, reverse=True)
        return [
            (holding.symbol, holding.company_name or self.market_data_service.resolve_company_name(holding.symbol))
            for holding in prioritized[:5]
        ]

    def _normalize_symbol_key(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        if normalized.endswith(".KS") or normalized.endswith(".KQ"):
            normalized = normalized.split(".", 1)[0]
        return normalized

    def _watchlist_snapshot_map(
        self,
        watchlist: list[MarketWatchSnapshot],
    ) -> dict[str, MarketWatchSnapshot]:
        return {
            self._normalize_symbol_key(snapshot.symbol): snapshot
            for snapshot in watchlist
        }

    def _keyword_reason(self, keyword: str) -> str:
        return f"사용자가 요청한 키워드 '{keyword}' 즉시 분석에서 자동 등록된 주문 제안입니다."

    def _text_contains_any(self, text: str, candidates: list[str]) -> bool:
        lowered_text = text.casefold()
        return any(candidate and candidate.casefold() in lowered_text for candidate in candidates)

    def _has_direct_keyword_relevance(
        self,
        *,
        requested_keyword: str,
        symbol: str,
        company_name: str,
        recommendation_keyword: str,
        rationale: str,
        article_lookup: dict[str, Any],
        source_article_ids: list[str],
    ) -> bool:
        normalized_symbol = self._normalize_symbol_key(symbol)
        company_candidates = [company_name.strip(), normalized_symbol]
        keyword_candidates = [requested_keyword.strip(), recommendation_keyword.strip()]

        rationale_supports_keyword = self._text_contains_any(rationale, keyword_candidates)
        rationale_supports_company = self._text_contains_any(rationale, company_candidates)

        article_supports_company = False
        article_supports_keyword = False
        for article_id in source_article_ids:
            article = article_lookup.get(article_id)
            if article is None:
                continue
            article_text = f"{article.title} {article.summary}".strip()
            if self._text_contains_any(article_text, keyword_candidates):
                article_supports_keyword = True
            if self._text_contains_any(article_text, company_candidates):
                article_supports_company = True

        return article_supports_company and (article_supports_keyword or (rationale_supports_keyword and rationale_supports_company))

    def _register_keyword_proposal(
        self,
        *,
        keyword: str,
        recommendation: dict[str, Any],
    ) -> int | None:
        if recommendation["signal_type"] not in {"buy", "sell"}:
            return None
        if not recommendation["executable"]:
            return None
        if recommendation["suggested_quantity"] is None or recommendation["suggested_amount"] is None:
            return None
        if recommendation["reference_price"] is None:
            return None

        reason = self._keyword_reason(keyword)
        existing = self.repository.find_pending_order_proposal(
            symbol=str(recommendation["symbol"]),
            proposal_type=str(recommendation["signal_type"]),
            reason=reason,
        )
        if existing is not None:
            return int(existing["id"])

        return self.repository.save_order_proposal(
            {
                "signal_ids": [],
                "symbol": recommendation["symbol"],
                "company_name": recommendation["company_name"],
                "proposal_type": recommendation["signal_type"],
                "quantity": int(recommendation["suggested_quantity"]),
                "reference_price": float(recommendation["reference_price"]),
                "target_amount": float(recommendation["suggested_amount"]),
                "score": int(recommendation["score"]),
                "hold_days": int(recommendation["hold_days"]),
                "rationale": str(recommendation["rationale"]),
                "status": "pending_approval",
                "reason": reason,
            }
        )

    def _build_keyword_recommendation(
        self,
        *,
        requested_keyword: str,
        recommendation: Any,
        account: AccountSnapshot,
        watchlist_map: dict[str, MarketWatchSnapshot],
        article_lookup: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized_symbol = self._normalize_symbol_key(str(recommendation.symbol))
        resolved_symbol = self._normalize_orderable_symbol(normalized_symbol)
        watch_snapshot = watchlist_map.get(normalized_symbol)
        holding = account.holding_for_symbol(normalized_symbol)
        company_name = self._resolve_company_name(normalized_symbol, account=account) or recommendation.company_name

        if not self._has_direct_keyword_relevance(
            requested_keyword=requested_keyword,
            symbol=normalized_symbol,
            company_name=company_name,
            recommendation_keyword=str(recommendation.keyword),
            rationale=str(recommendation.rationale),
            article_lookup=article_lookup,
            source_article_ids=list(recommendation.source_article_ids),
        ):
            return None

        reference_price = self.market_data_service.get_latest_price(normalized_symbol)
        if reference_price <= 0:
            if holding is not None and holding.current_price > 0:
                reference_price = holding.current_price
            elif watch_snapshot is not None and watch_snapshot.last_close > 0:
                reference_price = watch_snapshot.last_close

        suggested_quantity: int | None = None
        suggested_amount: float | None = None
        executable = False
        execution_block_reason: str | None = None

        if recommendation.signal_type == "buy":
            if resolved_symbol is None:
                execution_block_reason = "키움 국내 주식 주문 코드가 아닌 종목입니다."
            elif watch_snapshot is None:
                execution_block_reason = "매수 가능 후보 데이터가 없어 추천 수량을 계산할 수 없습니다."
            elif recommendation.suspicious_volume or watch_snapshot.suspicious_volume:
                execution_block_reason = "이상 거래량이 감지되어 매수 추천에서 제외되었습니다."
            elif not watch_snapshot.stable_volume:
                execution_block_reason = "거래량이 일정하지 않아 매수 추천 조건을 충족하지 않습니다."
            elif watch_snapshot.max_affordable_quantity < 1:
                execution_block_reason = "현재 계좌 예수금으로 최소 1주도 매수할 수 없습니다."
            elif reference_price <= 0:
                execution_block_reason = "기준 가격을 확인할 수 없어 매수 수량을 계산할 수 없습니다."
            else:
                available_buying_power = self._available_buying_power(account)
                target_budget = min(
                    available_buying_power,
                    max(reference_price, account.total_equity * float(recommendation.allocation_ratio)),
                )
                suggested_quantity = min(
                    watch_snapshot.max_affordable_quantity,
                    max(1, floor(target_budget / reference_price)),
                )
                if suggested_quantity <= 0:
                    execution_block_reason = "계산 결과 매수 가능 수량이 0주입니다."
                else:
                    suggested_amount = round(suggested_quantity * reference_price, 2)
                    executable = True
        elif recommendation.signal_type == "sell":
            if resolved_symbol is None:
                execution_block_reason = "키움 국내 주식 주문 코드가 아닌 종목입니다."
            elif holding is None or holding.quantity <= 0:
                execution_block_reason = "현재 계좌에 보유 중인 종목이 아니라 매도 추천을 만들 수 없습니다."
            elif reference_price <= 0:
                execution_block_reason = "기준 가격을 확인할 수 없어 매도 수량을 계산할 수 없습니다."
            else:
                available_quantity = holding.available_quantity or holding.quantity
                target_value = max(reference_price, account.total_equity * abs(float(recommendation.allocation_ratio)))
                suggested_quantity = min(available_quantity, max(1, floor(target_value / reference_price)))
                if suggested_quantity <= 0:
                    execution_block_reason = "계산 결과 매도 가능 수량이 0주입니다."
                else:
                    suggested_amount = round(suggested_quantity * reference_price, 2)
                    executable = True
        else:
            execution_block_reason = "근거가 충분하지 않아 관망으로 분류되었습니다."

        if recommendation.signal_type in {"buy", "sell"} and not executable:
            return None

        return {
            "symbol": resolved_symbol or normalized_symbol,
            "company_name": company_name,
            "keyword": recommendation.keyword,
            "score": int(recommendation.score),
            "signal_type": recommendation.signal_type,
            "allocation_ratio": float(recommendation.allocation_ratio),
            "hold_days": int(recommendation.hold_days),
            "recent_volume": int(recommendation.recent_volume),
            "volume_ratio": float(recommendation.volume_ratio),
            "suspicious_volume": bool(recommendation.suspicious_volume),
            "stable_volume": bool(watch_snapshot.stable_volume) if watch_snapshot is not None else False,
            "recorded_date": recommendation.recorded_date,
            "rationale": recommendation.rationale,
            "reference_price": round(reference_price, 2) if reference_price > 0 else None,
            "suggested_quantity": suggested_quantity,
            "suggested_amount": suggested_amount,
            "max_affordable_quantity": watch_snapshot.max_affordable_quantity if watch_snapshot is not None else 0,
            "currently_held_quantity": holding.quantity if holding is not None else 0,
            "executable": executable,
            "execution_block_reason": execution_block_reason,
            "registered_proposal_id": None,
            "source_names": [
                article_lookup[article_id].source_name
                for article_id in recommendation.source_article_ids
                if article_id in article_lookup
            ],
            "source_urls": [
                article_lookup[article_id].url
                for article_id in recommendation.source_article_ids
                if article_id in article_lookup
            ],
        }

    def _build_proposal_payload_from_signal(
        self,
        *,
        signal: dict[str, Any],
        account: AccountSnapshot,
        reason: str,
    ) -> dict[str, Any]:
        signal_type = str(signal["signal_type"])
        if signal_type not in {"buy", "sell"}:
            raise ValueError("관망 시그널은 직접 주문할 수 없습니다.")
        if signal.get("suspicious_volume"):
            raise ValueError("이상 거래량이 감지된 시그널은 직접 주문할 수 없습니다.")
        if self._normalize_orderable_symbol(str(signal["symbol"])) is None:
            raise ValueError("키움 국내 주식 코드로 주문할 수 없는 종목입니다.")

        total_equity = account.total_equity or self.settings.kiwoom_fallback_cash_balance
        if total_equity <= 0:
            raise RuntimeError("계좌 총자산을 확인할 수 없어 주문 수량을 계산할 수 없습니다.")

        price = self.market_data_service.get_latest_price(str(signal["symbol"]))
        if price <= 0:
            raise RuntimeError("현재가를 조회하지 못해 주문 수량을 계산할 수 없습니다.")

        min_trade_value = total_equity * self.settings.min_account_impact_ratio
        max_total_trade_value = total_equity * self.settings.account_max_exposure_ratio
        allocation_ratio = abs(float(signal["allocation_ratio"]))

        if signal_type == "buy":
            available_buy_value = self._available_buying_power(account)
            if available_buy_value <= 0:
                raise ValueError("현재 계좌 기준으로 추가 매수 가능 금액이 없습니다.")
            target_value = min(total_equity * allocation_ratio, available_buy_value)
            if target_value < min_trade_value:
                raise ValueError("현재 시그널은 최소 주문 기준 금액에 미달하여 바로 매수할 수 없습니다.")
            quantity = floor(target_value / price)
            if quantity <= 0:
                raise ValueError("현재가 기준으로 계산된 매수 수량이 0주입니다.")
        else:
            holding = account.holding_for_symbol(str(signal["symbol"]))
            if holding is None or holding.quantity <= 0:
                raise ValueError("현재 계좌에 해당 종목이 없어 매도할 수 없습니다.")
            target_value = total_equity * allocation_ratio
            if target_value < min_trade_value:
                raise ValueError("현재 시그널은 최소 주문 기준 금액에 미달하여 바로 매도할 수 없습니다.")
            available_quantity = holding.available_quantity or holding.quantity
            quantity = min(available_quantity, max(1, floor(target_value / price)))
            if quantity <= 0:
                raise ValueError("현재 계좌 기준으로 매도 가능한 수량이 없습니다.")

        return {
            "signal_ids": [int(signal["id"])],
            "symbol": str(signal["symbol"]),
            "company_name": self._resolve_company_name(str(signal["symbol"]), account=account) or str(signal["company_name"]),
            "proposal_type": signal_type,
            "quantity": quantity,
            "reference_price": round(price, 2),
            "target_amount": round(quantity * price, 2),
            "score": int(signal["score"]),
            "hold_days": int(signal["hold_days"]),
            "rationale": str(signal["rationale"]),
            "status": "pending_approval",
            "reason": reason,
        }

    def _is_news_cycle_due(self, now: datetime) -> bool:
        last_cycle = self.repository.get_state("last_news_cycle_at")
        if not last_cycle:
            return True
        try:
            previous = datetime.fromisoformat(last_cycle)
        except ValueError:
            return True
        return now - previous >= timedelta(minutes=self.settings.news_scan_interval_minutes)

    def sync_holdings(self) -> AccountSnapshot:
        if not self.kiwoom_service.enabled:
            snapshot = self._fallback_account_snapshot()
            self.repository.replace_broker_holdings(
                account_no=snapshot.account_no,
                holdings=snapshot.holdings,
                updated_at=self.clock.now().isoformat(),
            )
            return snapshot

        try:
            snapshot = self.kiwoom_service.fetch_account_snapshot()
        except Exception as exc:
            self._log(
                event_type="error",
                level="error",
                message="Failed to sync Kiwoom holdings.",
                metadata={"error": str(exc)},
            )
            return self._fallback_account_snapshot()

        synced_at = self.clock.now().isoformat()
        self.repository.replace_broker_holdings(
            account_no=snapshot.account_no,
            holdings=snapshot.holdings,
            updated_at=synced_at,
        )
        self.repository.set_state("last_holdings_sync_at", synced_at)
        if snapshot.account_no:
            self.repository.set_state("active_account_no", snapshot.account_no)
        return snapshot

    def run_cycle(self) -> None:
        now = self.clock.now()
        if not self.clock.is_operating_window(now):
            return

        account_snapshot = self.sync_holdings()

        if self._is_news_cycle_due(now):
            self.run_news_cycle(force=False, account_snapshot=account_snapshot)

        self.build_order_proposals(account_snapshot=account_snapshot)

    def run_news_cycle(self, *, force: bool, account_snapshot: AccountSnapshot | None = None) -> int:
        now = self.clock.now()
        if not force and not self.clock.is_operating_window(now):
            return 0

        previous_signature = self.repository.get_state("last_news_signature")
        previous_summary = self.repository.get_state("last_ai_summary")
        snapshot = account_snapshot or self.sync_holdings()
        selection = self.news_service.collect_articles(
            previous_context_signature=previous_signature,
            preferred_companies=self._preferred_news_companies(snapshot),
        )
        self.repository.set_state("last_news_cycle_at", now.isoformat())

        if selection.skip_reason:
            self._log(event_type="scan", message=selection.skip_reason)
            return 0

        if not selection.articles:
            self._log(event_type="scan", message="News scan completed without actionable articles.")
            return 0

        if not self.openai_service.enabled:
            self._log(
                event_type="error",
                level="error",
                message="OPENAI_API_KEY (or OPEN_API_KEY) is not configured.",
            )
            return 0

        watchlist = self.market_data_service.build_watchlist(
            buying_power=self._available_buying_power(snapshot),
            held_symbols={holding.symbol for holding in snapshot.holdings},
            preferred_symbols=[holding.symbol for holding in snapshot.holdings],
        )

        plan = self.openai_service.analyze(
            now_iso=now.isoformat(),
            articles=selection.articles,
            watchlist=watchlist,
            account=snapshot,
            previous_summary=previous_summary,
            operation_window=self.clock.is_operating_window(now),
        )

        self.repository.set_state("last_news_signature", selection.signature)
        self.repository.set_state("last_ai_summary", plan.market_sentiment_summary)
        self.repository.clear_market_signals()

        created = 0
        article_lookup = {article.article_id: article for article in selection.articles}
        for recommendation in plan.recommendations:
            resolved_company_name = self._resolve_company_name(recommendation.symbol, account=snapshot)
            signal_id = self.repository.save_market_signal(
                {
                    "symbol": recommendation.symbol,
                    "company_name": resolved_company_name or recommendation.company_name,
                    "keyword": recommendation.keyword,
                    "score": recommendation.score,
                    "signal_type": recommendation.signal_type,
                    "allocation_ratio": recommendation.allocation_ratio,
                    "hold_days": recommendation.hold_days,
                    "recent_volume": recommendation.recent_volume,
                    "volume_ratio": recommendation.volume_ratio,
                    "suspicious_volume": recommendation.suspicious_volume,
                    "recorded_date": recommendation.recorded_date,
                    "rationale": recommendation.rationale,
                    "source_names": [
                        article_lookup[article_id].source_name
                        for article_id in recommendation.source_article_ids
                        if article_id in article_lookup
                    ],
                    "source_urls": [
                        article_lookup[article_id].url
                        for article_id in recommendation.source_article_ids
                        if article_id in article_lookup
                    ],
                    "source_article_ids": recommendation.source_article_ids,
                }
            )
            created += 1
            self._log(
                event_type=recommendation.signal_type,
                message=f"AI stored a {recommendation.signal_type} signal for {recommendation.symbol}.",
                metadata={"signal_id": signal_id, "score": recommendation.score},
            )

        if plan.skip_reason:
            self._log(event_type="scan", message=plan.skip_reason)

        return created

    def analyze_keyword(self, *, keyword: str) -> dict[str, Any]:
        normalized_keyword = keyword.strip()
        if len(normalized_keyword) < 2:
            raise ValueError("키워드는 2글자 이상 입력해주세요.")

        now = self.clock.now()
        account = self.sync_holdings()
        articles = self.news_service.collect_articles_for_keyword(
            keyword=normalized_keyword,
            limit=self.settings.news_max_articles,
        )
        if not articles:
            return {
                "keyword": normalized_keyword,
                "analyzed_at": now.isoformat(),
                "summary": f"'{normalized_keyword}' 관련 최신 뉴스를 찾지 못했습니다.",
                "skip_reason": "관련 최신 뉴스가 충분하지 않습니다.",
                "articles": [],
                "recommendations": [],
                "account": {
                    "account_no": account.account_no,
                    "cash_balance": round(account.cash_balance, 2),
                    "holdings_value": round(account.holdings_value, 2),
                    "total_equity": round(account.total_equity, 2),
                    "available_buying_power": round(self._available_buying_power(account), 2),
                    "holding_count": len(account.holdings),
                },
            }

        if not self.openai_service.enabled:
            raise RuntimeError("OPENAI_API_KEY (or OPEN_API_KEY) is not configured.")

        watchlist = self.market_data_service.build_watchlist(
            buying_power=self._available_buying_power(account),
            held_symbols={holding.symbol for holding in account.holdings},
            preferred_symbols=[holding.symbol for holding in account.holdings],
        )
        watchlist_map = self._watchlist_snapshot_map(watchlist)
        plan = self.openai_service.analyze_keyword(
            now_iso=now.isoformat(),
            keyword=normalized_keyword,
            articles=articles,
            watchlist=watchlist,
            account=account,
        )

        article_lookup = {article.article_id: article for article in articles}
        recommendations = [
            payload
            for payload in (
                self._build_keyword_recommendation(
                    recommendation=recommendation,
                    account=account,
                    watchlist_map=watchlist_map,
                    article_lookup=article_lookup,
                )
                for recommendation in plan.recommendations
            )
            if payload is not None
        ]

        self._log(
            event_type="keyword-analysis",
            message=f"Completed keyword analysis for {normalized_keyword}.",
            metadata={
                "keyword": normalized_keyword,
                "article_count": len(articles),
                "recommendation_count": len(recommendations),
            },
        )

        return {
            "keyword": normalized_keyword,
            "analyzed_at": now.isoformat(),
            "summary": plan.market_sentiment_summary,
            "skip_reason": plan.skip_reason,
            "articles": [
                {
                    "article_id": article.article_id,
                    "title": article.title,
                    "source_name": article.source_name,
                    "url": article.url,
                    "published_at": article.published_at.isoformat(),
                    "summary": article.summary,
                    "region": article.region,
                    "topic": article.topic,
                }
                for article in articles
            ],
            "recommendations": recommendations,
            "account": {
                "account_no": account.account_no,
                "cash_balance": round(account.cash_balance, 2),
                "holdings_value": round(account.holdings_value, 2),
                "total_equity": round(account.total_equity, 2),
                "available_buying_power": round(self._available_buying_power(account), 2),
                "holding_count": len(account.holdings),
            },
        }

    def analyze_keyword(self, *, keyword: str) -> dict[str, Any]:
        normalized_keyword = keyword.strip()
        if len(normalized_keyword) < 2:
            raise ValueError("키워드는 2글자 이상 입력해주세요.")

        now = self.clock.now()
        account = self.sync_holdings()
        articles = self.news_service.collect_articles_for_keyword(
            keyword=normalized_keyword,
            limit=self.settings.news_max_articles,
        )
        if not articles:
            return {
                "keyword": normalized_keyword,
                "analyzed_at": now.isoformat(),
                "summary": f"'{normalized_keyword}' 관련 최신 뉴스를 찾지 못했습니다.",
                "skip_reason": "관련 최신 뉴스가 충분하지 않습니다.",
                "articles": [],
                "recommendations": [],
                "registered_proposals": [],
                "account": {
                    "account_no": account.account_no,
                    "cash_balance": round(account.cash_balance, 2),
                    "holdings_value": round(account.holdings_value, 2),
                    "total_equity": round(account.total_equity, 2),
                    "available_buying_power": round(self._available_buying_power(account), 2),
                    "holding_count": len(account.holdings),
                },
            }

        if not self.openai_service.enabled:
            raise RuntimeError("OPENAI_API_KEY (or OPEN_API_KEY) is not configured.")

        watchlist = self.market_data_service.build_watchlist(
            buying_power=self._available_buying_power(account),
            held_symbols={holding.symbol for holding in account.holdings},
            preferred_symbols=[holding.symbol for holding in account.holdings],
        )
        watchlist_map = self._watchlist_snapshot_map(watchlist)
        plan = self.openai_service.analyze_keyword(
            now_iso=now.isoformat(),
            keyword=normalized_keyword,
            articles=articles,
            watchlist=watchlist,
            account=account,
        )

        article_lookup = {article.article_id: article for article in articles}
        recommendations = [
            payload
            for payload in (
                self._build_keyword_recommendation(
                    requested_keyword=normalized_keyword,
                    recommendation=recommendation,
                    account=account,
                    watchlist_map=watchlist_map,
                    article_lookup=article_lookup,
                )
                for recommendation in plan.recommendations
            )
            if payload is not None
        ]

        registered_proposals: list[int] = []
        for recommendation in recommendations:
            proposal_id = self._register_keyword_proposal(
                keyword=normalized_keyword,
                recommendation=recommendation,
            )
            recommendation["registered_proposal_id"] = proposal_id
            if proposal_id is not None:
                registered_proposals.append(proposal_id)

        self._log(
            event_type="keyword-analysis",
            message=f"Completed keyword analysis for {normalized_keyword}.",
            metadata={
                "keyword": normalized_keyword,
                "article_count": len(articles),
                "recommendation_count": len(recommendations),
                "registered_proposal_count": len(registered_proposals),
            },
        )

        return {
            "keyword": normalized_keyword,
            "analyzed_at": now.isoformat(),
            "summary": plan.market_sentiment_summary,
            "skip_reason": plan.skip_reason,
            "articles": [
                {
                    "article_id": article.article_id,
                    "title": article.title,
                    "source_name": article.source_name,
                    "url": article.url,
                    "published_at": article.published_at.isoformat(),
                    "summary": article.summary,
                    "region": article.region,
                    "topic": article.topic,
                }
                for article in articles
            ],
            "recommendations": recommendations,
            "registered_proposals": registered_proposals,
            "account": {
                "account_no": account.account_no,
                "cash_balance": round(account.cash_balance, 2),
                "holdings_value": round(account.holdings_value, 2),
                "total_equity": round(account.total_equity, 2),
                "available_buying_power": round(self._available_buying_power(account), 2),
                "holding_count": len(account.holdings),
            },
        }

    def build_order_proposals(self, *, account_snapshot: AccountSnapshot | None = None) -> int:
        pending = self.repository.list_unprocessed_signals()
        if not pending:
            return 0

        account = account_snapshot or self.sync_holdings()
        total_equity = account.total_equity or self.settings.kiwoom_fallback_cash_balance
        if total_equity <= 0:
            self._log(
                event_type="error",
                level="error",
                message="Unable to size proposals because account equity is unavailable.",
            )
            return 0

        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "symbol": "",
                "company_name": "",
                "signal_ids": [],
                "net_allocation": 0.0,
                "latest": None,
            }
        )

        for signal in pending:
            if signal["signal_type"] == "hold":
                self.repository.mark_signal_processed(signal["id"], status="ignored")
                continue
            if signal["suspicious_volume"]:
                self.repository.mark_signal_processed(signal["id"], status="blocked")
                self._log(
                    event_type="proposal",
                    message=f"Skipped {signal['symbol']} because the volume spike looks suspicious.",
                    metadata={"signal_id": signal["id"]},
                )
                continue

            if self._normalize_orderable_symbol(signal["symbol"]) is None:
                self.repository.mark_signal_processed(signal["id"], status="unsupported-symbol")
                self._log(
                    event_type="proposal",
                    message=f"Skipped {signal['symbol']} because it is not a Kiwoom domestic orderable symbol.",
                    metadata={"signal_id": signal["id"]},
                )
                continue

            bucket = grouped[signal["symbol"]]
            bucket["symbol"] = signal["symbol"]
            bucket["company_name"] = signal["company_name"]
            bucket["signal_ids"].append(signal["id"])
            bucket["latest"] = signal
            signed_ratio = signal["allocation_ratio"] if signal["signal_type"] == "buy" else -signal["allocation_ratio"]
            bucket["net_allocation"] += signed_ratio

        max_total_trade_value = total_equity * self.settings.account_max_exposure_ratio
        min_trade_value = total_equity * self.settings.min_account_impact_ratio
        available_buy_value = min(
            self._available_buying_power(account),
            max(0.0, max_total_trade_value - account.holdings_value),
        )

        buy_groups = [group for group in grouped.values() if group["net_allocation"] > 0]
        total_requested_buy_value = sum(total_equity * group["net_allocation"] for group in buy_groups)
        buy_scale = 1.0
        if total_requested_buy_value > 0 and total_requested_buy_value > available_buy_value:
            buy_scale = available_buy_value / total_requested_buy_value

        created = 0
        for group in grouped.values():
            latest = group["latest"]
            if latest is None:
                continue

            signal_ids = group["signal_ids"]
            price = self.market_data_service.get_latest_price(group["symbol"])
            if price <= 0:
                self.repository.mark_signals_processed(signal_ids, status="failed")
                self._log(
                    event_type="error",
                    level="error",
                    message=f"Price lookup failed for {group['symbol']}.",
                    metadata={"signal_ids": signal_ids},
                )
                continue

            if group["net_allocation"] > 0:
                target_value = total_equity * group["net_allocation"] * buy_scale
                if target_value < min_trade_value:
                    self.repository.mark_signals_processed(signal_ids, status="skipped")
                    continue
                quantity = floor(target_value / price)
                if quantity <= 0:
                    self.repository.mark_signals_processed(signal_ids, status="skipped")
                    continue

                proposal_id = self.repository.save_order_proposal(
                    {
                        "signal_ids": signal_ids,
                        "symbol": group["symbol"],
                        "company_name": group["company_name"],
                        "proposal_type": "buy",
                        "quantity": quantity,
                        "reference_price": round(price, 2),
                        "target_amount": round(quantity * price, 2),
                        "score": int(latest["score"]),
                        "hold_days": int(latest["hold_days"]),
                        "rationale": latest["rationale"],
                        "status": "pending_approval",
                        "reason": "Awaiting user approval before Kiwoom order submission.",
                    }
                )
                self.repository.mark_signals_processed(signal_ids, status="proposed")
                self.repository.set_state("last_processed_signal_id", str(max(signal_ids)))
                self._log(
                    event_type="proposal",
                    message=f"Created a buy proposal for {group['symbol']}.",
                    metadata={"proposal_id": proposal_id, "quantity": quantity, "signal_ids": signal_ids},
                )
                created += 1
                continue

            if group["net_allocation"] < 0:
                holding = account.holding_for_symbol(group["symbol"])
                if holding is None or holding.quantity <= 0:
                    self.repository.mark_signals_processed(signal_ids, status="not-held")
                    self._log(
                        event_type="proposal",
                        message=f"Skipped sell proposal for {group['symbol']} because the account does not hold it.",
                        metadata={"signal_ids": signal_ids},
                    )
                    continue

                target_value = total_equity * abs(group["net_allocation"])
                if target_value < min_trade_value:
                    self.repository.mark_signals_processed(signal_ids, status="skipped")
                    continue
                quantity = min(holding.available_quantity or holding.quantity, max(1, floor(target_value / price)))
                if quantity <= 0:
                    self.repository.mark_signals_processed(signal_ids, status="skipped")
                    continue

                proposal_id = self.repository.save_order_proposal(
                    {
                        "signal_ids": signal_ids,
                        "symbol": group["symbol"],
                        "company_name": group["company_name"],
                        "proposal_type": "sell",
                        "quantity": quantity,
                        "reference_price": round(price, 2),
                        "target_amount": round(quantity * price, 2),
                        "score": int(latest["score"]),
                        "hold_days": int(latest["hold_days"]),
                        "rationale": latest["rationale"],
                        "status": "pending_approval",
                        "reason": "Awaiting user approval before Kiwoom order submission.",
                    }
                )
                self.repository.mark_signals_processed(signal_ids, status="proposed")
                self.repository.set_state("last_processed_signal_id", str(max(signal_ids)))
                self._log(
                    event_type="proposal",
                    message=f"Created a sell proposal for {group['symbol']}.",
                    metadata={"proposal_id": proposal_id, "quantity": quantity, "signal_ids": signal_ids},
                )
                created += 1

        return created

    def approve_proposal(self, proposal_id: int) -> dict[str, Any]:
        proposal = self.repository.get_order_proposal(proposal_id)
        if proposal is None:
            raise ValueError("The requested proposal does not exist.")
        if proposal["status"] != "pending_approval":
            raise ValueError("Only pending proposals can be approved.")
        signal_ids = [int(signal_id) for signal_id in proposal.get("signal_ids", [])]
        if not self.clock.is_market_open():
            raise ValueError("The market is closed. Try approving the proposal during market hours.")

        account = self.sync_holdings()
        if proposal["proposal_type"] == "sell":
            holding = account.holding_for_symbol(proposal["symbol"])
            if holding is None or holding.quantity <= 0:
                self.repository.update_order_proposal(
                    proposal_id,
                    status="failed",
                    approved_at=self.clock.now().isoformat(),
                    last_error="The symbol is no longer held in the Kiwoom account.",
                )
                self.repository.update_signals_execution_status(signal_ids, status="failed")
                raise ValueError("The symbol is no longer held in the Kiwoom account.")
            available_quantity = holding.available_quantity or holding.quantity
            if available_quantity < int(proposal["quantity"]):
                self.repository.update_order_proposal(
                    proposal_id,
                    status="failed",
                    approved_at=self.clock.now().isoformat(),
                    last_error="Available quantity is smaller than the proposed sell quantity.",
                )
                self.repository.update_signals_execution_status(signal_ids, status="failed")
                raise ValueError("Available quantity is smaller than the proposed sell quantity.")

        result = self.kiwoom_service.place_market_order(
            symbol=str(proposal["symbol"]),
            company_name=str(proposal["company_name"]),
            action=str(proposal["proposal_type"]),
            quantity=int(proposal["quantity"]),
            reference_price=float(proposal["reference_price"]),
        )

        approved_at = self.clock.now().isoformat()
        if not result.success:
            self.repository.update_order_proposal(
                proposal_id,
                status="failed",
                approved_at=approved_at,
                last_error=result.message,
            )
            self.repository.update_signals_execution_status(signal_ids, status="failed")
            self._log(
                event_type="error",
                level="error",
                message=f"Failed to submit Kiwoom order for proposal {proposal_id}.",
                metadata={"proposal_id": proposal_id, "error": result.message},
            )
            raise RuntimeError(result.message)

        pnl = None
        if proposal["proposal_type"] == "sell":
            holding = account.holding_for_symbol(proposal["symbol"])
            if holding is not None and holding.average_price > 0:
                pnl = round(
                    (float(proposal["reference_price"]) - holding.average_price) * int(proposal["quantity"]),
                    2,
                )

        self.repository.update_order_proposal(
            proposal_id,
            status="executed",
            reason="Approved by the user and submitted to the Kiwoom API.",
            broker_order_id=result.broker_order_id,
            last_error=None,
            approved_at=approved_at,
            executed_at=approved_at,
        )
        self.repository.update_signals_execution_status(signal_ids, status="executed")
        self.repository.save_trade_execution(
            {
                "symbol": proposal["symbol"],
                "company_name": proposal["company_name"],
                "trade_type": proposal["proposal_type"],
                "quantity": proposal["quantity"],
                "price": proposal["reference_price"],
                "total_amount": proposal["target_amount"],
                "pnl": pnl,
                "status": "submitted",
                "broker_order_id": result.broker_order_id,
                "signal_id": proposal["signal_ids"][-1] if proposal["signal_ids"] else None,
                "position_ids": [],
                "notes": result.message,
                "executed_at": approved_at,
            }
        )
        self._log(
            event_type="order",
            message=f"Submitted a Kiwoom {proposal['proposal_type']} order for {proposal['symbol']}.",
            metadata={
                "proposal_id": proposal_id,
                "broker_order_id": result.broker_order_id,
                "quantity": proposal["quantity"],
            },
        )
        self.sync_holdings()
        updated = self.repository.get_order_proposal(proposal_id)
        if updated is None:
            raise RuntimeError("The proposal was updated but could not be reloaded.")
        return updated

    def execute_signal(self, signal_id: int) -> dict[str, Any]:
        signal = self.repository.get_market_signal(signal_id)
        if signal is None:
            raise ValueError("요청한 AI 시그널이 존재하지 않습니다.")
        if signal["signal_type"] == "hold":
            raise ValueError("관망 시그널은 직접 주문할 수 없습니다.")
        if signal["execution_status"] == "proposed":
            raise ValueError("이미 승인 대기 중인 주문 제안이 있는 시그널입니다.")
        if signal["execution_status"] == "executed":
            raise ValueError("이미 주문이 접수된 시그널입니다.")
        if not self.clock.is_market_open():
            raise ValueError("장이 열려 있을 때만 바로 주문을 실행할 수 있습니다.")

        account = self.sync_holdings()
        proposal_id = self.repository.save_order_proposal(
            self._build_proposal_payload_from_signal(
                signal=signal,
                account=account,
                reason="사용자가 AI 시그널에서 직접 주문 버튼을 눌러 즉시 전송했습니다.",
            )
        )
        self.repository.update_signals_execution_status([signal_id], status="proposed")
        self._log(
            event_type="proposal",
            message=f"Created an instant {signal['signal_type']} proposal from signal {signal_id}.",
            metadata={"proposal_id": proposal_id, "signal_id": signal_id},
        )
        return self.approve_proposal(proposal_id)

    def reject_proposal(self, proposal_id: int) -> dict[str, Any]:
        proposal = self.repository.get_order_proposal(proposal_id)
        if proposal is None:
            raise ValueError("The requested proposal does not exist.")
        if proposal["status"] != "pending_approval":
            raise ValueError("Only pending proposals can be rejected.")

        self.repository.update_order_proposal(
            proposal_id,
            status="rejected",
            reason="Rejected by the user.",
            approved_at=self.clock.now().isoformat(),
        )
        self.repository.update_signals_execution_status(
            [int(signal_id) for signal_id in proposal.get("signal_ids", [])],
            status="rejected",
        )
        self._log(
            event_type="proposal",
            message=f"Rejected proposal {proposal_id} for {proposal['symbol']}.",
            metadata={"proposal_id": proposal_id, "symbol": proposal["symbol"]},
        )
        updated = self.repository.get_order_proposal(proposal_id)
        if updated is None:
            raise RuntimeError("The proposal was updated but could not be reloaded.")
        return updated
