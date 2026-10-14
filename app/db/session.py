from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def create_engine(database_url: str, *, use_pool: bool = True) -> AsyncEngine:
    """Create an async engine.

    use_pool=False is meant for short-lived event loops (Celery tasks run via asyncio.run):
    asyncpg connections are bound to the loop that created them, so they cannot be reused.
    """
    if use_pool:
        return create_async_engine(database_url, pool_pre_ping=True)
    return create_async_engine(database_url, poolclass=NullPool)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
