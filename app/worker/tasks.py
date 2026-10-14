import asyncio
import logging

import aiohttp
from celery import shared_task

from app.clients.deribit import DeribitClient
from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.domain.tickers import Ticker
from app.repositories.prices import PriceRepository
from app.services.price_collector import PriceCollector
from app.worker.celery_app import COLLECT_PRICES_TASK

logger = logging.getLogger(__name__)


async def run_price_collection(settings: Settings) -> int:
    """Composition root of a single collection run. Returns the number of saved prices."""
    # Each Celery run gets its own event loop, so the engine lives only for this run.
    engine = create_engine(settings.database_url, use_pool=False)
    session_factory = create_session_factory(engine)
    timeout = aiohttp.ClientTimeout(total=settings.deribit_timeout_seconds)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as http_session,
            session_factory() as db_session,
            db_session.begin(),
        ):
            collector = PriceCollector(
                provider=DeribitClient(http_session, settings.deribit_base_url),
                repository=PriceRepository(db_session),
            )
            snapshots = await collector.collect(Ticker)
    finally:
        await engine.dispose()
    return len(snapshots)


@shared_task(name=COLLECT_PRICES_TASK)
def collect_index_prices() -> int:
    saved = asyncio.run(run_price_collection(Settings()))
    logger.info("Saved %d index prices", saved)
    return saved
