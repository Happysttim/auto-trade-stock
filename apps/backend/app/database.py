from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .schemas import Holding


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS market_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            company_name TEXT NOT NULL,
            keyword TEXT NOT NULL,
            score INTEGER NOT NULL,
            signal_type TEXT NOT NULL,
            allocation_ratio REAL NOT NULL,
            hold_days INTEGER NOT NULL,
            recent_volume INTEGER NOT NULL,
            volume_ratio REAL NOT NULL,
            suspicious_volume INTEGER NOT NULL DEFAULT 0,
            recorded_date TEXT NOT NULL,
            rationale TEXT NOT NULL,
            source_names TEXT NOT NULL,
            source_urls TEXT NOT NULL,
            source_article_ids TEXT NOT NULL,
            created_at TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            processed_at TEXT,
            execution_status TEXT NOT NULL DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS trade_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            company_name TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            total_amount REAL NOT NULL,
            pnl REAL,
            status TEXT NOT NULL,
            broker_order_id TEXT,
            signal_id INTEGER,
            position_ids TEXT NOT NULL,
            notes TEXT,
            executed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS order_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_ids TEXT NOT NULL,
            symbol TEXT NOT NULL,
            company_name TEXT NOT NULL,
            proposal_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reference_price REAL NOT NULL,
            target_amount REAL NOT NULL,
            score INTEGER NOT NULL,
            hold_days INTEGER NOT NULL,
            rationale TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            broker_order_id TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            approved_at TEXT,
            executed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS broker_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_no TEXT,
            symbol TEXT NOT NULL,
            company_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            available_quantity INTEGER NOT NULL,
            average_price REAL NOT NULL,
            current_price REAL NOT NULL,
            market_value REAL NOT NULL,
            pnl REAL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            metadata TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS service_state (
            state_key TEXT PRIMARY KEY,
            state_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_market_signals_processed ON market_signals (processed, id);
        CREATE INDEX IF NOT EXISTS idx_trade_executions_executed_at ON trade_executions (executed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_order_proposals_status ON order_proposals (status, id DESC);
        CREATE INDEX IF NOT EXISTS idx_broker_holdings_account_symbol ON broker_holdings (account_no, symbol);
        CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs (created_at DESC);
        """

        with self.connection() as connection:
            connection.executescript(schema)

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        for key in ("source_names", "source_urls", "source_article_ids", "metadata", "position_ids", "signal_ids"):
            if key in payload:
                payload[key] = json.loads(payload[key] or "[]")
        if "suspicious_volume" in payload:
            payload["suspicious_volume"] = bool(payload["suspicious_volume"])
        if "processed" in payload:
            payload["processed"] = bool(payload["processed"])
        return payload

    def count_market_signals(self) -> int:
        with self.connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM market_signals").fetchone()
        return 0 if row is None else int(row["count"])

    def save_market_signal(self, payload: dict[str, Any]) -> int:
        statement = """
        INSERT INTO market_signals (
            symbol, company_name, keyword, score, signal_type, allocation_ratio,
            hold_days, recent_volume, volume_ratio, suspicious_volume,
            recorded_date, rationale, source_names, source_urls, source_article_ids,
            created_at, processed, execution_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            payload["symbol"],
            payload["company_name"],
            payload["keyword"],
            payload["score"],
            payload["signal_type"],
            payload["allocation_ratio"],
            payload["hold_days"],
            payload["recent_volume"],
            payload["volume_ratio"],
            1 if payload.get("suspicious_volume", False) else 0,
            payload["recorded_date"],
            payload["rationale"],
            json.dumps(payload.get("source_names", []), ensure_ascii=False),
            json.dumps(payload.get("source_urls", []), ensure_ascii=False),
            json.dumps(payload.get("source_article_ids", []), ensure_ascii=False),
            payload.get("created_at", utc_now_iso()),
            1 if payload.get("processed", False) else 0,
            payload.get("execution_status", "pending"),
        )

        with self._lock, self.connection() as connection:
            cursor = connection.execute(statement, values)
            return int(cursor.lastrowid)

    def list_market_signals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM market_signals ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_unprocessed_signals(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM market_signals WHERE processed = 0 ORDER BY id ASC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def mark_signal_processed(self, signal_id: int, *, status: str) -> None:
        with self._lock, self.connection() as connection:
            connection.execute(
                """
                UPDATE market_signals
                SET processed = 1, processed_at = ?, execution_status = ?
                WHERE id = ?
                """,
                (utc_now_iso(), status, signal_id),
            )

    def mark_signals_processed(self, signal_ids: list[int], *, status: str) -> None:
        if not signal_ids:
            return
        now = utc_now_iso()
        placeholders = ",".join("?" for _ in signal_ids)
        with self._lock, self.connection() as connection:
            connection.execute(
                f"""
                UPDATE market_signals
                SET processed = 1, processed_at = ?, execution_status = ?
                WHERE id IN ({placeholders})
                """,
                (now, status, *signal_ids),
            )

    def save_trade_execution(self, payload: dict[str, Any]) -> int:
        statement = """
        INSERT INTO trade_executions (
            symbol, company_name, trade_type, quantity, price, total_amount,
            pnl, status, broker_order_id, signal_id, position_ids, notes, executed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            payload["symbol"],
            payload["company_name"],
            payload["trade_type"],
            payload["quantity"],
            payload["price"],
            payload["total_amount"],
            payload.get("pnl"),
            payload["status"],
            payload.get("broker_order_id"),
            payload.get("signal_id"),
            json.dumps(payload.get("position_ids", []), ensure_ascii=False),
            payload.get("notes"),
            payload.get("executed_at", utc_now_iso()),
        )
        with self._lock, self.connection() as connection:
            cursor = connection.execute(statement, values)
            return int(cursor.lastrowid)

    def list_trade_executions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM trade_executions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def save_order_proposal(self, payload: dict[str, Any]) -> int:
        statement = """
        INSERT INTO order_proposals (
            signal_ids, symbol, company_name, proposal_type, quantity,
            reference_price, target_amount, score, hold_days, rationale,
            status, reason, broker_order_id, last_error, created_at,
            approved_at, executed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            json.dumps(payload.get("signal_ids", []), ensure_ascii=False),
            payload["symbol"],
            payload["company_name"],
            payload["proposal_type"],
            payload["quantity"],
            payload["reference_price"],
            payload["target_amount"],
            payload["score"],
            payload["hold_days"],
            payload["rationale"],
            payload.get("status", "pending_approval"),
            payload.get("reason"),
            payload.get("broker_order_id"),
            payload.get("last_error"),
            payload.get("created_at", utc_now_iso()),
            payload.get("approved_at"),
            payload.get("executed_at"),
        )
        with self._lock, self.connection() as connection:
            cursor = connection.execute(statement, values)
            return int(cursor.lastrowid)

    def list_order_proposals(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM order_proposals
                ORDER BY
                    CASE WHEN status = 'pending_approval' THEN 0 ELSE 1 END,
                    id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count_order_proposals(self, *, status: str | None = None) -> int:
        with self.connection() as connection:
            if status is None:
                row = connection.execute("SELECT COUNT(*) AS count FROM order_proposals").fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM order_proposals WHERE status = ?",
                    (status,),
                ).fetchone()
        return 0 if row is None else int(row["count"])

    def get_order_proposal(self, proposal_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM order_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
        return None if row is None else self._row_to_dict(row)

    def update_order_proposal(self, proposal_id: int, **changes: Any) -> None:
        if not changes:
            return

        allowed = {
            "status",
            "reason",
            "broker_order_id",
            "last_error",
            "approved_at",
            "executed_at",
        }
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in changes.items():
            if key not in allowed:
                continue
            assignments.append(f"{key} = ?")
            values.append(value)

        if not assignments:
            return

        values.append(proposal_id)
        with self._lock, self.connection() as connection:
            connection.execute(
                f"UPDATE order_proposals SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )

    def replace_broker_holdings(
        self,
        *,
        account_no: str | None,
        holdings: list[Holding],
        updated_at: str | None = None,
    ) -> None:
        stamped_at = updated_at or utc_now_iso()
        with self._lock, self.connection() as connection:
            if account_no:
                connection.execute("DELETE FROM broker_holdings WHERE account_no = ?", (account_no,))
            else:
                connection.execute("DELETE FROM broker_holdings")

            for holding in holdings:
                connection.execute(
                    """
                    INSERT INTO broker_holdings (
                        account_no, symbol, company_name, quantity, available_quantity,
                        average_price, current_price, market_value, pnl, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_no,
                        holding.symbol,
                        holding.company_name,
                        holding.quantity,
                        holding.available_quantity,
                        holding.average_price,
                        holding.current_price,
                        holding.market_value,
                        holding.pnl,
                        stamped_at,
                    ),
                )

    def list_broker_holdings(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM broker_holdings
                ORDER BY market_value DESC, symbol ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def save_system_log(
        self,
        *,
        event_type: str,
        level: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO system_logs (event_type, level, message, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    level,
                    message,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    utc_now_iso(),
                ),
            )
            return int(cursor.lastrowid)

    def list_system_logs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM system_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_state(self, key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT state_value FROM service_state WHERE state_key = ?",
                (key,),
            ).fetchone()
        return None if row is None else str(row["state_value"])

    def set_state(self, key: str, value: str) -> None:
        now = utc_now_iso()
        with self._lock, self.connection() as connection:
            connection.execute(
                """
                INSERT INTO service_state (state_key, state_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    state_value = excluded.state_value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
