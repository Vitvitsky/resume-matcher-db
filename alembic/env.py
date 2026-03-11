"""
Alembic environment configuration для resume-matcher-db.

DATABASE_URL читается из переменной окружения.
Модели импортируются из resume-matcher-engine для поддержки autogenerate.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from alembic import context

# Загружаем .env из директории resume-matcher-db/
load_dotenv(Path(__file__).parents[1] / ".env")

# Добавляем путь к resume-matcher-engine для импорта моделей (autogenerate)
_repo_root = Path(__file__).parents[2]
_engine_path = _repo_root / "resume-matcher-engine"
if _engine_path.exists():
    sys.path.insert(0, str(_engine_path))

try:
    from src.database.models import Base
    target_metadata = Base.metadata
except ImportError:
    # autogenerate не будет работать, но миграции из versions/ применятся
    target_metadata = None

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_url() -> str:
    """Читает DATABASE_URL из окружения или alembic.ini."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        url = config.get_main_option("sqlalchemy.url", "")
    if not url:
        raise ValueError(
            "DATABASE_URL не задан. "
            "Скопируйте .env.example → .env и укажите DATABASE_URL."
        )
    return url


def run_migrations_offline() -> None:
    """Генерация SQL без подключения к БД (--sql режим)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применение миграций с подключением к БД."""
    url = get_url()
    connectable = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
