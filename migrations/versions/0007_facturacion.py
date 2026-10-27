# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""facturas y cobros

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

DINERO = sa.Numeric(precision=14, scale=2)
TASA = sa.Numeric(precision=20, scale=10)


def upgrade():
    op.create_table(
        'facturas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proyecto_id', sa.Integer(), sa.ForeignKey('proyectos.id', name='fk_facturas_proyecto'), nullable=False),
        sa.Column('etapa_id', sa.Integer(), sa.ForeignKey('etapas.id', name='fk_facturas_etapa', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('numero', sa.String(length=40), nullable=True),
        sa.Column('concepto', sa.String(length=200), nullable=True),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('vencimiento', sa.Date(), nullable=True),
        sa.Column('moneda', sa.String(length=3), nullable=False),
        sa.Column('importe_neto', DINERO, nullable=False),
        sa.Column('impuesto', DINERO, nullable=False, server_default='0'),
        sa.Column('cotizacion', TASA, nullable=False, server_default='1'),
        sa.Column('neto_base', DINERO, nullable=False),
        sa.Column('anulada', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('es_ejemplo', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('creado', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('actualizado', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_facturas_proyecto_id', 'facturas', ['proyecto_id'])
    op.create_index('ix_facturas_fecha', 'facturas', ['fecha'])
    op.create_table(
        'cobros',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('factura_id', sa.Integer(), sa.ForeignKey('facturas.id', name='fk_cobros_factura', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('importe', DINERO, nullable=False),
        sa.Column('cotizacion', TASA, nullable=False, server_default='1'),
        sa.Column('importe_base', DINERO, nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_cobros_factura_id', 'cobros', ['factura_id'])
    op.create_index('ix_cobros_fecha', 'cobros', ['fecha'])


def downgrade():
    op.drop_table('cobros')
    op.drop_table('facturas')
