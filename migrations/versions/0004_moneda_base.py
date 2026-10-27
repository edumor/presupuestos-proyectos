# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""moneda base configurable y más datos de la empresa

- Las columnas *_usd pasan a *_base: guardan importes en la moneda base
  configurada (ARS por defecto en instalaciones nuevas).
- Las cotizaciones pasan de "1 USD = X moneda" (por_usd) a
  "1 moneda = X moneda base" (valor). En instalaciones existentes la base
  sigue siendo USD, así que valor = 1 / por_usd y nada cambia de valor.
- Datos de la empresa: localidad, provincia, código postal, país y teléfonos.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

RENOMBRES = {
    'proyectos': [('precio_usd', 'precio_base')],
    'presupuestos': [('tasa_estructura_usd', 'tasa_estructura_base'), ('costo_usd', 'costo_base'),
                     ('precio_usd', 'precio_base')],
    'presupuesto_items': [('costo_hora_usd', 'costo_hora_base')],
    'costos_externos': [('importe_usd', 'importe_base')],
    'tareas': [('costo_hora_usd', 'costo_hora_base'), ('costo_previsto_usd', 'costo_previsto_base')],
    'horas_reales': [('costo_hora_usd', 'costo_hora_base')],
}

EMPRESA = [
    sa.Column('empresa_localidad', sa.String(length=120), nullable=True),
    sa.Column('empresa_provincia', sa.String(length=120), nullable=True),
    sa.Column('empresa_cp', sa.String(length=20), nullable=True),
    sa.Column('empresa_pais', sa.String(length=80), nullable=True),
    sa.Column('empresa_telefonos', sa.String(length=160), nullable=True),
]

# Se usa ALTER TABLE nativo de SQLite (RENAME/ADD/DROP COLUMN, SQLite >= 3.35) en lugar del modo
# "batch", que recrea las tablas y falla con claves foráneas activas en bases con datos.


def _sql(sentencia: str) -> None:
    op.get_bind().execute(sa.text(sentencia))


def upgrade():
    con = op.get_bind()
    # Instalaciones con datos pero sin fila de configuración: dejar la base que usaban (USD)
    hay_datos = any(con.execute(sa.text(f"SELECT 1 FROM {t} LIMIT 1")).first()
                    for t in ('personas', 'proyectos', 'cotizaciones', 'costos_fijos'))
    if hay_datos and not con.execute(sa.text("SELECT 1 FROM configuracion WHERE id = 1")).first():
        _sql("INSERT INTO configuracion (id, moneda_base, horas_anuales, utilizacion, margen_defecto, margen_alerta,"
             " impuesto_defecto, ss_empresa_defecto, horas_autonomos_anuales, zona_horaria, validez_dias)"
             " VALUES (1, 'USD', 1760, 0.7, 0.35, 0.25, 0, 0.32, 1500, 'America/New_York', 30)")

    for tabla, cols in RENOMBRES.items():
        for viejo, nuevo in cols:
            _sql(f"ALTER TABLE {tabla} RENAME COLUMN {viejo} TO {nuevo}")
    _sql("ALTER TABLE presupuestos DROP COLUMN usd_eur")
    _sql("ALTER TABLE presupuestos DROP COLUMN usd_gbp")

    _sql("ALTER TABLE cotizaciones ADD COLUMN valor NUMERIC(20, 10)")
    _sql("UPDATE cotizaciones SET valor = 1.0 / por_usd")
    _sql("ALTER TABLE cotizaciones DROP COLUMN por_usd")

    for c in EMPRESA:
        _sql(f"ALTER TABLE configuracion ADD COLUMN {c.name} VARCHAR({c.type.length})")


def downgrade():
    for c in reversed(EMPRESA):
        _sql(f"ALTER TABLE configuracion DROP COLUMN {c.name}")
    _sql("ALTER TABLE cotizaciones ADD COLUMN por_usd NUMERIC(14, 6)")
    _sql("UPDATE cotizaciones SET por_usd = 1.0 / valor")
    _sql("ALTER TABLE cotizaciones DROP COLUMN valor")
    _sql("ALTER TABLE presupuestos ADD COLUMN usd_eur NUMERIC(14, 6)")
    _sql("ALTER TABLE presupuestos ADD COLUMN usd_gbp NUMERIC(14, 6)")
    for tabla, cols in RENOMBRES.items():
        for viejo, nuevo in cols:
            _sql(f"ALTER TABLE {tabla} RENAME COLUMN {nuevo} TO {viejo}")
