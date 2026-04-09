from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from .runtime import ServiceContainer

api_blueprint = Blueprint("api", __name__)


def get_container() -> ServiceContainer:
    return current_app.extensions["container"]


@api_blueprint.get("/health")
def health_check():
    container = get_container()
    now = container.clock.now()
    return jsonify(
        {
            "status": "ok",
            "service": "auto-trade-stock-backend",
            "now": now.isoformat(),
            "operating_window": container.clock.is_operating_window(now),
            "market_open": container.clock.is_market_open(now),
        }
    )


@api_blueprint.get("/api/status")
def get_status():
    container = get_container()
    now = container.clock.now()
    repository = container.repository

    return jsonify(
        {
            "service_now": now.isoformat(),
            "operating_window": container.clock.is_operating_window(now),
            "market_open": container.clock.is_market_open(now),
            "last_news_cycle_at": repository.get_state("last_news_cycle_at"),
            "last_ai_summary": repository.get_state("last_ai_summary"),
            "latest_signal_count": repository.count_market_signals(),
            "pending_proposal_count": repository.count_order_proposals(status="pending_approval"),
            "holding_count": len(repository.list_broker_holdings(limit=200)),
            "last_holdings_sync_at": repository.get_state("last_holdings_sync_at"),
            "active_account_no": repository.get_state("active_account_no"),
            "last_processed_signal_id": repository.get_state("last_processed_signal_id"),
        }
    )


@api_blueprint.get("/api/signals")
def get_signals():
    limit = int(request.args.get("limit", "50"))
    return jsonify(get_container().repository.list_market_signals(limit=limit))


@api_blueprint.get("/api/proposals")
def get_proposals():
    limit = int(request.args.get("limit", "100"))
    return jsonify(get_container().repository.list_order_proposals(limit=limit))


@api_blueprint.get("/api/holdings")
def get_holdings():
    limit = int(request.args.get("limit", "100"))
    return jsonify(get_container().repository.list_broker_holdings(limit=limit))


@api_blueprint.get("/api/trades")
def get_trades():
    limit = int(request.args.get("limit", "50"))
    return jsonify(get_container().repository.list_trade_executions(limit=limit))


@api_blueprint.get("/api/logs")
def get_logs():
    limit = int(request.args.get("limit", "100"))
    return jsonify(get_container().repository.list_system_logs(limit=limit))


@api_blueprint.post("/api/proposals/<int:proposal_id>/approve")
def approve_proposal(proposal_id: int):
    container = get_container()
    try:
        proposal = container.trading_engine.approve_proposal(proposal_id)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502
    return jsonify({"status": "ok", "proposal": proposal})


@api_blueprint.post("/api/proposals/<int:proposal_id>/reject")
def reject_proposal(proposal_id: int):
    container = get_container()
    try:
        proposal = container.trading_engine.reject_proposal(proposal_id)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    return jsonify({"status": "ok", "proposal": proposal})


@api_blueprint.post("/api/tasks/run-cycle")
def run_cycle():
    container = get_container()
    container.trading_engine.run_cycle()
    return jsonify({"status": "ok", "triggered_at": datetime.utcnow().isoformat()})


@api_blueprint.post("/api/tasks/scan-news")
def scan_news():
    container = get_container()
    created_count = container.trading_engine.run_news_cycle(force=True)
    return jsonify({"status": "ok", "created_signals": created_count})


@api_blueprint.post("/api/tasks/sync-holdings")
def sync_holdings():
    container = get_container()
    snapshot = container.trading_engine.sync_holdings()
    return jsonify(
        {
            "status": "ok",
            "account_no": snapshot.account_no,
            "holding_count": len(snapshot.holdings),
            "cash_balance": snapshot.cash_balance,
        }
    )
