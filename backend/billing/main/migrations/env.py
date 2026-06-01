from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from cm_shared.db import Base
from cm_shared.settings import get_base_settings
from main.models import Plan, Subscription, WebhookEvent  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_base_settings().sync_database_url)
target_metadata = Base.metadata


VERSION_TABLE = "alembic_version_billing"


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=VERSION_TABLE,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
