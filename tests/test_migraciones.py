# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Una instalación existente (base USD, versión 0.3) se actualiza sin perder valores."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text

from app.config import resource_root


def _alembic(conn, destino: str, bajar: bool = False) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(resource_root() / "migrations"))
    cfg.attributes["connection"] = conn
    (command.downgrade if bajar else command.upgrade)(cfg, destino)


def test_actualiza_base_usd_con_datos(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'vieja.db'}")
    event.listen(eng, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    with eng.begin() as c:
        _alembic(c, "0003")
        c.execute(text("INSERT INTO configuracion (id, moneda_base, horas_anuales, utilizacion, margen_defecto,"
                       " margen_alerta, impuesto_defecto, ss_empresa_defecto, horas_autonomos_anuales, zona_horaria,"
                       " validez_dias) VALUES (1, 'USD', 1760, 0.7, 0.35, 0.25, 0, 0.32, 1500, 'America/New_York', 30)"))
        c.execute(text("INSERT INTO cotizaciones (fecha, moneda, por_usd) VALUES ('2026-10-01', 'EUR', 0.8)"))
        c.execute(text("INSERT INTO clientes (nombre, moneda_mostrar, es_ejemplo) VALUES ('C', 'USD', 0)"))
        c.execute(text("INSERT INTO proyectos (cliente_id, nombre, estado, margen, impuesto, precio_usd, es_ejemplo)"
                       " VALUES (1, 'P', 'en_curso', 0.3, 0, 1234.5, 0)"))
    with eng.begin() as c:
        _alembic(c, "head")
        assert c.execute(text("SELECT moneda_base FROM configuracion")).scalar() == "USD"
        assert c.execute(text("SELECT valor FROM cotizaciones")).scalar() == pytest.approx(1.25)
        assert c.execute(text("SELECT precio_base FROM proyectos")).scalar() == pytest.approx(1234.5)
    with eng.begin() as c:  # y se puede volver atrás
        _alembic(c, "0003", bajar=True)
        assert c.execute(text("SELECT por_usd FROM cotizaciones")).scalar() == pytest.approx(0.8)
