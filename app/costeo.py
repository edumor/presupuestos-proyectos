# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Costeo con datos de la base: cotización vigente, costo por hora y tasa de estructura."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import calculos
from .models import Configuracion, CostoFijo, Cotizacion, Periodicidad, Persona, TipoPersona


class FaltaCotizacion(Exception):
    def __init__(self, moneda: str):
        self.moneda = moneda
        super().__init__(f"No hay cotización cargada para {moneda}. Cargala en Cotizaciones.")


def config(db: Session) -> Configuracion:
    cfg = db.get(Configuracion, 1)
    if cfg is None:
        cfg = Configuracion(id=1)
        db.add(cfg)
        db.commit()
    return cfg


def cotizacion_vigente(db: Session, moneda: str, a_fecha: date | None = None) -> Cotizacion | None:
    """Última cotización cargada en o antes de `a_fecha` (hoy por defecto)."""
    a_fecha = a_fecha or date.today()
    return db.scalars(
        select(Cotizacion).where(Cotizacion.moneda == moneda, Cotizacion.fecha <= a_fecha)
        .order_by(Cotizacion.fecha.desc()).limit(1)
    ).first()


def moneda_base(db: Session) -> str:
    return config(db).moneda_base or "ARS"


def base_por_unidad(db: Session, moneda: str, a_fecha: date | None = None) -> float:
    """Cuántas unidades de la moneda base vale 1 unidad de `moneda`."""
    if moneda == moneda_base(db):
        return 1.0
    cot = cotizacion_vigente(db, moneda, a_fecha)
    if cot is None:
        raise FaltaCotizacion(moneda)
    return float(cot.valor)


def a_base(db: Session, importe: float, moneda: str, a_fecha: date | None = None) -> float:
    return float(importe) * base_por_unidad(db, moneda, a_fecha)


def _anual(c: CostoFijo) -> float:
    return float(c.importe) * (12 if c.periodicidad == Periodicidad.mensual else 1)


def costos_fijos_vigentes(db: Session, a_fecha: date | None = None) -> list[CostoFijo]:
    a_fecha = a_fecha or date.today()
    return [c for c in db.scalars(select(CostoFijo)).all()
            if (c.vigente_desde is None or c.vigente_desde <= a_fecha)
            and (c.vigente_hasta is None or c.vigente_hasta >= a_fecha)]


def costo_fijo_anual_base(db: Session, c: CostoFijo, a_fecha: date | None = None) -> float:
    return a_base(db, _anual(c), c.moneda, a_fecha)


def estructura(db: Session, a_fecha: date | None = None) -> dict:
    cfg = config(db)
    fijos = sum(costo_fijo_anual_base(db, c, a_fecha) for c in costos_fijos_vigentes(db, a_fecha))
    n_emp = len(db.scalars(select(Persona).where(Persona.activo, Persona.tipo == TipoPersona.empleado)).all())
    h_emp = n_emp * calculos.horas_facturables_empleado(cfg.horas_anuales, cfg.utilizacion)
    h_aut = cfg.horas_autonomos_anuales
    horas = h_emp + h_aut
    tasa = calculos.tasa_estructura(fijos, horas) if horas > 0 else 0.0
    return dict(costos_fijos_anuales_base=fijos, horas_empleados=h_emp, horas_autonomos=h_aut,
                horas_facturables_anuales=horas, tasa_estructura_base=tasa)


def costo_hora(db: Session, p: Persona, a_fecha: date | None = None, tasa: float | None = None) -> dict:
    cfg = config(db)
    base = cfg.moneda_base
    fx = base_por_unidad(db, p.moneda, a_fecha)
    if tasa is None:
        tasa = estructura(db, a_fecha)["tasa_estructura_base"]
    if p.tipo == TipoPersona.empleado:
        ss = p.ss_empresa if p.ss_empresa is not None else cfg.ss_empresa_defecto
        directo = calculos.costo_directo_empleado(float(p.sueldo_bruto_anual), ss, fx,
                                                  cfg.horas_anuales, cfg.utilizacion)
        detalle = (f"{float(p.sueldo_bruto_anual):,.0f} {p.moneda}/año × (1 + {ss:.2%} SS) × {fx:,.4f} {base}/{p.moneda}"
                   f" ÷ ({cfg.horas_anuales:,.0f} h × {cfg.utilizacion:.0%})")
    else:
        directo = calculos.costo_directo_autonomo(float(p.tarifa_hora), fx)
        detalle = f"{float(p.tarifa_hora):,.2f} {p.moneda}/h × {fx:,.4f} {base}/{p.moneda}"
    return dict(persona_id=p.id, nombre=p.nombre, tipo=p.tipo, moneda=p.moneda, base_por_unidad=fx,
                costo_directo_base=directo, tasa_estructura_base=tasa, costo_total_base=directo + tasa,
                detalle=detalle)
