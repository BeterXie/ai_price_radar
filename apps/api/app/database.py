from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# SQLite serializes writers per file and has no server-side pool, so the
# server pool knobs do not apply there. PostgreSQL keeps a bounded pool whose
# timeout is short enough that a saturated pool fails the request instead of
# parking an anyio worker thread for the default 30 seconds.
pool_args: dict[str, object] = {}
if not is_sqlite:
    pool_args = {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_pool_max_overflow,
        "pool_timeout": settings.db_pool_timeout_seconds,
        "pool_recycle": settings.db_pool_recycle_seconds,
    }

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    **pool_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except BaseException:
        # An endpoint that raises mid-transaction would otherwise hand a
        # connection with an open transaction back to the pool, leaving the
        # row locks behind as `idle in transaction`.
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()
