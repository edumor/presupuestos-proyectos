# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""datos de la consultora para documentos

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

COLUMNAS = [
    sa.Column('empresa_nombre', sa.String(length=160), nullable=True),
    sa.Column('empresa_direccion', sa.String(length=255), nullable=True),
    sa.Column('empresa_email', sa.String(length=160), nullable=True),
    sa.Column('empresa_web', sa.String(length=160), nullable=True),
    sa.Column('empresa_id_fiscal', sa.String(length=60), nullable=True),
    sa.Column('validez_dias', sa.Integer(), nullable=False, server_default='30'),
    sa.Column('condiciones', sa.Text(), nullable=True),
]


def upgrade():
    with op.batch_alter_table('configuracion', schema=None) as batch_op:
        for c in COLUMNAS:
            batch_op.add_column(c)


def downgrade():
    with op.batch_alter_table('configuracion', schema=None) as batch_op:
        for c in reversed(COLUMNAS):
            batch_op.drop_column(c.name)
