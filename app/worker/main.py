"""Entrypoint for the Celery CLI: celery -A app.worker.main worker / beat.

Celery's CLI needs a ready application object to import, so this module is the single
place where an instance is created at import time. All other code uses the factory.
"""

from app.worker.celery_app import create_celery_app

celery_app = create_celery_app()
