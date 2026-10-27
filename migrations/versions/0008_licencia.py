# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""licencia y aviso de actualizaciones

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    con = op.get_bind()
    con.execute(sa.text("ALTER TABLE configuracion ADD COLUMN licencia TEXT"))
    con.execute(sa.text("ALTER TABLE configuracion ADD COLUMN buscar_actualizaciones BOOLEAN NOT NULL DEFAULT 1"))


def downgrade():
    con = op.get_bind()
    con.execute(sa.text("ALTER TABLE configuracion DROP COLUMN buscar_actualizaciones"))
    con.execute(sa.text("ALTER TABLE configuracion DROP COLUMN licencia"))
