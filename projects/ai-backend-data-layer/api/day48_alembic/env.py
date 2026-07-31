"""Day48 — minimal Alembic env.py (deployment control plane ONLY).

Per the Day48 discipline this stays MINIMAL: migration DB configuration, the
target ``Base.metadata`` (Day46), and Alembic execution. It does NOT build the
FastAPI app, does NOT import the Day47 request/Job UoW, and does NOT share a
business Session. Alembic is a deployment/control-plane concern, distinct from a
request/Job UoW, and the app must never self-run migrations on startup.

Database URL resolution (highest priority first):
    1. ``alembic -x db_url=<url>``  (per-invocation override)
    2. env var ``DAY48_ALEMBIC_DATABASE_URL``
    3. ``sqlalchemy.url`` in ``alembic.ini`` — a NON-CREDENTIAL PLACEHOLDER used
       ONLY for offline ``--sql`` rendering (dialect selection; it never connects
       and is NOT a production connection configuration).

Offline mode (``alembic upgrade --sql``) renders DDL text using the resolved URL's
dialect and NEVER connects — static/offline evidence, NOT PostgreSQL runtime
proof. Online mode connects to the resolved URL supplied out-of-band (never a
committed credential).

This module is import-safe: outside an Alembic run the migration block is skipped,
so ``resolve_database_url`` can be unit-tested without a database or a live context.
"""

from __future__ import annotations

import os
import sys
from typing import Mapping, Optional

from alembic import context

# Make the Day46 mapping importable (the api/ directory is this file's grandparent).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_database_url(
    x_arguments: Mapping[str, str],
    environ: Mapping[str, str],
    ini_url: Optional[str],
) -> str:
    """Resolve the migration database URL by explicit priority (PURE + testable):

        alembic -x db_url=...  >  env DAY48_ALEMBIC_DATABASE_URL  >  alembic.ini sqlalchemy.url (offline placeholder)

    The ini value is only a non-credential offline-render placeholder; a real run
    supplies a URL via -x or the environment (never a committed credential)."""
    x_url = x_arguments.get("db_url")
    if x_url:
        return x_url
    env_url = environ.get("DAY48_ALEMBIC_DATABASE_URL")
    if env_url:
        return env_url
    if ini_url:
        return ini_url
    raise RuntimeError(
        "No migration database URL: pass `-x db_url=...`, set "
        "DAY48_ALEMBIC_DATABASE_URL, or configure sqlalchemy.url (offline only)."
    )


def _resolved_url() -> str:
    return resolve_database_url(
        context.get_x_argument(as_dictionary=True),
        os.environ,
        context.config.get_main_option("sqlalchemy.url"),
    )


def run_migrations_offline() -> None:
    # Day46 Base.metadata is the AUTOGENERATE INPUT, NOT the database authority.
    from day46_orm_mapping import Base

    context.configure(
        url=_resolved_url(),
        target_metadata=Base.metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine, pool

    from day46_orm_mapping import Base

    connectable = create_engine(_resolved_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


def _in_alembic_run() -> bool:
    """True only when Alembic has established the context proxy (i.e. during an
    actual migration command). Outside a run the proxy raises, so importing this
    module for tests does not execute any migration."""
    try:
        context.is_offline_mode()
        return True
    except Exception:
        return False


if _in_alembic_run():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
