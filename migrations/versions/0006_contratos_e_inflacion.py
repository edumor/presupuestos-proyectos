# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""contratos en otra moneda, ajuste por IPC y aumento previsto de costos

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

COLUMNAS = [
    ('proyectos', 'moneda_contrato', 'VARCHAR(3)'),
    ('proyectos', 'precio_contrato', 'NUMERIC(14, 2)'),
    ('proyectos', 'ajuste_indice', 'VARCHAR(10)'),
    ('proyectos', 'ajuste_cada_meses', 'INTEGER'),
    ('proyectos', 'ajuste_mes_base', 'DATE'),
    ('presupuestos', 'moneda_contrato', 'VARCHAR(3)'),
    ('configuracion', 'aumento_costos_mensual', 'FLOAT NOT NULL DEFAULT 0'),
]


def _sql(s: str) -> None:
    op.get_bind().execute(sa.text(s))


def upgrade():
    for tabla, col, tipo in COLUMNAS:
        _sql(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
    op.create_table('indices_ipc',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('mes', sa.Date(), nullable=False),
                    sa.Column('variacion', sa.Float(), nullable=False),
                    sa.Column('fuente', sa.String(length=40), nullable=True),
                    sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('mes'))


def downgrade():
    op.drop_table('indices_ipc')
    for tabla, col, _ in reversed(COLUMNAS):
        _sql(f"ALTER TABLE {tabla} DROP COLUMN {col}")
