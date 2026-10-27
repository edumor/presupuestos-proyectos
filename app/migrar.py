# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Aplica las migraciones pendientes de Alembic al iniciar la aplicación."""
from alembic import command
from alembic.config import Config

from .config import resource_root
from .database import engine


def migrar() -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(resource_root() / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
