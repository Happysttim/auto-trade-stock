from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import floor
from typing import Any

from ..config import Settings
from ..database import Database
from ..schemas import AccountSnapshot
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
        selection = self.news_service.collect_articles(previous_context_signature=previous_signature)
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

        watchlist = self.market_data_service.build_watchlist()
        snapshot = account_snapshot or self.sync_holdings()

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

        created = 0
        article_lookup = {article.article_id: article for article in selection.articles}
        for recommendation in plan.recommendations:
            signal_id = self.repository.save_market_signal(
                {
                    "symbol": recommendation.symbol,
                    "company_name": recommendation.company_name,
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
        available_buy_value = max(0.0, max_total_trade_value - account.holdings_value)

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
                raise ValueError("The symbol is no longer held in the Kiwoom account.")
            available_quantity = holding.available_quantity or holding.quantity
            if available_quantity < int(proposal["quantity"]):
                self.repository.update_order_proposal(
                    proposal_id,
                    status="failed",
                    approved_at=self.clock.now().isoformat(),
                    last_error="Available quantity is smaller than the proposed sell quantity.",
                )
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
        self._log(
            event_type="proposal",
            message=f"Rejected proposal {proposal_id} for {proposal['symbol']}.",
            metadata={"proposal_id": proposal_id, "symbol": proposal["symbol"]},
        )
        updated = self.repository.get_order_proposal(proposal_id)
        if updated is None:
            raise RuntimeError("The proposal was updated but could not be reloaded.")
        return updated
