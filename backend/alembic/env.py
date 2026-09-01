"""Alembic environment wired to Reknew Orbit configuration and metadata."""

from __future__ import annotations

from logging.config import fileConfig
import importlib
import pkgutil

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base
import app.models as models_package


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def _load_all_models() -> None:
    """Populate Base.metadata without importing the FastAPI application."""
    for module in pkgutil.iter_modules(models_package.__path__, f"{models_package.__name__}."):
        importlib.import_module(module.name)


_load_all_models()
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=settings.DATABASE_URL.startswith("sqlite"),
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
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
