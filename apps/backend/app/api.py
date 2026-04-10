from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from .runtime import ServiceContainer

api_blueprint = Blueprint("api", __name__)


def get_container() -> ServiceContainer:
    return current_app.extensions["container"]


def _json_error(message: str, status_code: int):
    return jsonify({"status": "error", "message": message}), status_code


def _task_error(container: ServiceContainer, task_name: str, exc: Exception, *, default_status: int = 500):
    status_code = int(getattr(exc, "status_code", default_status) or default_status)
    container.repository.save_system_log(
        event_type="task",
        level="error",
        message=f"{task_name} failed.",
        metadata={"error": str(exc), "status_code": status_code},
    )
    return _json_error(str(exc), status_code)


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


@api_blueprint.post("/api/analysis/keyword")
def analyze_keyword():
    container = get_container()
    payload = request.get_json(silent=True) or {}
    keyword = str(payload.get("keyword") or "").strip()
    if not keyword:
        return _json_error("키워드를 입력해주세요.", 400)

    try:
        result = container.trading_engine.analyze_keyword(keyword=keyword)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _task_error(container, "Keyword analysis", exc)

    return jsonify({"status": "ok", **result})


@api_blueprint.post("/api/signals/<int:signal_id>/execute")
def execute_signal(signal_id: int):
    container = get_container()
    try:
        proposal = container.trading_engine.execute_signal(signal_id)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except RuntimeError as exc:
        return _json_error(str(exc), 502)
    return jsonify(
        {
            "status": "ok",
            "message": "AI 시그널을 기준으로 키움 주문을 전송했습니다.",
            "proposal": proposal,
        }
    )


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
        return _json_error(str(exc), 400)
    except RuntimeError as exc:
        return _json_error(str(exc), 502)
    return jsonify({"status": "ok", "proposal": proposal})


@api_blueprint.post("/api/proposals/<int:proposal_id>/reject")
def reject_proposal(proposal_id: int):
    container = get_container()
    try:
        proposal = container.trading_engine.reject_proposal(proposal_id)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify({"status": "ok", "proposal": proposal})


@api_blueprint.post("/api/tasks/run-cycle")
def run_cycle():
    container = get_container()
    try:
        container.trading_engine.run_cycle()
    except Exception as exc:
        return _task_error(container, "Scheduled cycle", exc)
    return jsonify({"status": "ok", "triggered_at": datetime.utcnow().isoformat()})


@api_blueprint.post("/api/tasks/scan-news")
def scan_news():
    container = get_container()
    try:
        created_count = container.trading_engine.run_news_cycle(force=True)
    except Exception as exc:
        return _task_error(container, "Manual news scan", exc)
    return jsonify(
        {
            "status": "ok",
            "created_signals": created_count,
            "triggered_at": datetime.utcnow().isoformat(),
            "message": f"수동 뉴스 분석을 완료했습니다. 시그널 {created_count}건을 생성했습니다.",
        }
    )


@api_blueprint.post("/api/tasks/sync-holdings")
def sync_holdings():
    container = get_container()
    try:
        snapshot = container.trading_engine.sync_holdings()
    except Exception as exc:
        return _task_error(container, "Holdings sync", exc)
    return jsonify(
        {
            "status": "ok",
            "account_no": snapshot.account_no,
            "holding_count": len(snapshot.holdings),
            "cash_balance": snapshot.cash_balance,
            "triggered_at": datetime.utcnow().isoformat(),
            "message": f"보유 종목 동기화를 완료했습니다. {len(snapshot.holdings)}개 종목을 반영했습니다.",
        }
    )


@api_blueprint.post("/api/tasks/build-proposals")
def build_proposals():
    container = get_container()
    try:
        snapshot = container.trading_engine.sync_holdings()
        created_count = container.trading_engine.build_order_proposals(account_snapshot=snapshot)
    except Exception as exc:
        return _task_error(container, "Proposal build", exc)
    return jsonify(
        {
            "status": "ok",
            "created_proposals": created_count,
            "triggered_at": datetime.utcnow().isoformat(),
            "message": f"주문 제안 생성을 완료했습니다. 제안 {created_count}건을 만들었습니다.",
        }
    )


@api_blueprint.post("/api/tasks/run-analysis")
def run_analysis():
    container = get_container()
    try:
        snapshot = container.trading_engine.sync_holdings()
        created_signals = container.trading_engine.run_news_cycle(force=True, account_snapshot=snapshot)
        created_proposals = container.trading_engine.build_order_proposals(account_snapshot=snapshot)
    except Exception as exc:
        return _task_error(container, "Manual full analysis", exc)
    return jsonify(
        {
            "status": "ok",
            "created_signals": created_signals,
            "created_proposals": created_proposals,
            "holding_count": len(snapshot.holdings),
            "account_no": snapshot.account_no,
            "triggered_at": datetime.utcnow().isoformat(),
            "message": f"수동 분석을 완료했습니다. 시그널 {created_signals}건, 주문 제안 {created_proposals}건을 생성했습니다.",
        }
    )
