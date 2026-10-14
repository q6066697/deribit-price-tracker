from celery import Celery

from app.core.config import Settings

COLLECT_PRICES_TASK = "prices.collect_index_prices"


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Celery application factory (the CLI entrypoint is app.worker.main)."""
    settings = settings or Settings()
    interval = settings.price_fetch_interval_seconds

    celery_app = Celery("deribit_price_tracker", broker=settings.redis_url)
    celery_app.conf.update(
        include=["app.worker.tasks"],
        timezone="UTC",
        task_ignore_result=True,
        beat_schedule={
            "collect-index-prices-every-minute": {
                "task": COLLECT_PRICES_TASK,
                "schedule": float(interval),
                # A run that waited longer than one interval is stale: the next one is coming.
                "options": {"expires": interval},
            },
        },
    )
    return celery_app
