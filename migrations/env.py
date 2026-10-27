# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401
from app.config import db_url
from app.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", db_url())
target_metadata = Base.metadata


def run_migrations_online():
    connectable = config.attributes.get("connection")
    if connectable is None:
        connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                         prefix="sqlalchemy.", poolclass=pool.NullPool)
        with connectable.connect() as conn:
            context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(connection=connectable, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
