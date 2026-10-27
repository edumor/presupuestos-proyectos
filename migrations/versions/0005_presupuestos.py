# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""módulo de presupuestos: etapa y % en ítems, etapa sugerida en servicios

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

COLUMNAS = [
    ('servicios', 'etapa_sugerida', 'VARCHAR(120)'),
    ('presupuesto_items', 'etapa', 'VARCHAR(120)'),
    ('presupuesto_items', 'pct_sobre_total', 'FLOAT'),
]


def _sql(s: str) -> None:
    op.get_bind().execute(sa.text(s))


def upgrade():
    for tabla, col, tipo in COLUMNAS:
        _sql(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")


def downgrade():
    for tabla, col, _ in reversed(COLUMNAS):
        _sql(f"ALTER TABLE {tabla} DROP COLUMN {col}")
