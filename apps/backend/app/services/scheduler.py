from __future__ import annotations

import threading

from ..config import Settings
from ..database import Database
from .trading_engine import TradingEngine


class BackgroundScheduler:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: Database,
        trading_engine: TradingEngine,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.trading_engine = trading_engine
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="approval-trade-scheduler", daemon=True)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.repository.save_system_log(
            event_type="service",
            level="info",
            message="Background analysis scheduler started.",
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._started:
            return
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
        self.repository.save_system_log(
            event_type="service",
            level="info",
            message="Background analysis scheduler stopped.",
        )
        self._started = False

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.trading_engine.run_cycle()
            except Exception as exc:
                self.repository.save_system_log(
                    event_type="error",
                    level="error",
                    message="Unhandled exception in background scheduler.",
                    metadata={"error": str(exc)},
                )
            self._stop_event.wait(self.settings.service_loop_seconds)
