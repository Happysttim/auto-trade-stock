from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .database import Database
from .services.kiwoom_service import KiwoomBrokerService
from .services.market_data_service import MarketDataService
from .services.market_hours import MarketClock
from .services.news_service import NewsService
from .services.openai_service import OpenAIAnalysisService
from .services.scheduler import BackgroundScheduler
from .services.trading_engine import TradingEngine


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    repository: Database
    clock: MarketClock
    news_service: NewsService
    market_data_service: MarketDataService
    kiwoom_service: KiwoomBrokerService
    openai_service: OpenAIAnalysisService
    trading_engine: TradingEngine
    scheduler: BackgroundScheduler

    def shutdown(self) -> None:
        self.scheduler.stop()
        self.kiwoom_service.shutdown()


def build_container(settings: Settings) -> ServiceContainer:
    repository = Database(settings.db_path)
    repository.initialize()
    repository.clear_runtime_logs_and_ai_feed()

    clock = MarketClock(settings)
    market_data_service = MarketDataService(settings)
    news_service = NewsService(settings)
    kiwoom_service = KiwoomBrokerService(settings, repository)
    openai_service = OpenAIAnalysisService(settings)
    trading_engine = TradingEngine(
        settings=settings,
        repository=repository,
        clock=clock,
        news_service=news_service,
        market_data_service=market_data_service,
        kiwoom_service=kiwoom_service,
        openai_service=openai_service,
    )
    scheduler = BackgroundScheduler(
        settings=settings,
        repository=repository,
        trading_engine=trading_engine,
    )

    return ServiceContainer(
        settings=settings,
        repository=repository,
        clock=clock,
        news_service=news_service,
        market_data_service=market_data_service,
        kiwoom_service=kiwoom_service,
        openai_service=openai_service,
        trading_engine=trading_engine,
        scheduler=scheduler,
    )
