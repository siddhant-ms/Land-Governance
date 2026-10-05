from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (register tables)
from app.core.config import get_settings
from app.core.db import Base

target_metadata = Base.metadata


def _url() -> str:
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().database_url


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=conn.dialect.name == "sqlite",
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
