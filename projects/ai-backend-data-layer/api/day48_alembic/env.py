"""Day48 — minimal Alembic env.py (deployment control plane ONLY).

Per the Day48 discipline this stays MINIMAL: migration DB configuration, the
target ``Base.metadata`` (Day46), and Alembic execution. It does NOT build the
FastAPI app, does NOT import the Day47 request/Job UoW, and does NOT share a
business Session. Alembic is a deployment/control-plane concern, distinct from a
request/Job UoW, and the app must never self-run migrations on startup.

Offline mode (``alembic upgrade --sql``) renders DDL text using the PostgreSQL
dialect and never connects — it is static/offline evidence, NOT PostgreSQL runtime
proof. Online mode connects to a real database supplied out-of-band.
"""

from __future__ import annotations

import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the Day46 mapping importable (the api/ directory is this file's grandparent).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Day46 Base.metadata is the AUTOGENERATE INPUT (a candidate-diff source), NOT the
# database authority. PostgreSQL/the Day42 raw SQL remain the authority.
from day46_orm_mapping import Base  # noqa: E402

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
