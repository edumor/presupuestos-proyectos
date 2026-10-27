# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Precio vigente de un proyecto según su contrato y proyección de costos con inflación.

- Contrato en otra moneda (p. ej. USD): el precio vale en esa moneda; en moneda base se reexpresa
  con la cotización vigente a la fecha consultada.
- Contrato en moneda base con ajuste por IPC: el precio se actualiza cada N meses por la variación
  acumulada del IPC desde el mes base, hasta el último mes con dato publicado.
- Costos: el trabajo pendiente se proyecta con el aumento mensual previsto de sueldos y tarifas.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import costeo
from .models import IndiceIPC, Proyecto


def primer_dia(d: date) -> date:
    return d.replace(day=1)


def sumar_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def meses_entre(a: date, b: date) -> int:
    """Meses completos de calendario de a hasta b (por mes, sin días)."""
    return (b.year - a.year) * 12 + (b.month - a.month)


def factor_ipc(db: Session, mes_base: date, cada_meses: int, a_fecha: date) -> dict:
    """Factor de ajuste acumulado y el último mes considerado.

    En la fecha consultada se aplica el último ajuste vencido (cada `cada_meses` desde el mes base),
    con la variación del IPC desde el mes base hasta el mes anterior al del ajuste, que es el último
    publicado. Ejemplo: base diciembre, ajuste trimestral: en marzo se aplican enero y febrero.
    Si falta el dato de algún mes, se usa lo publicado hasta ese momento.
    """
    base = primer_dia(mes_base)
    cada = max(int(cada_meses or 1), 1)
    transcurridos = meses_entre(base, primer_dia(a_fecha))
    aplicados = (transcurridos // cada) * cada if transcurridos > 0 else 0
    variaciones = {i.mes: i.variacion for i in db.scalars(select(IndiceIPC).where(IndiceIPC.mes > base))}
    factor, hasta, faltan = 1.0, None, 0
    # el ajuste de un mes usa el IPC publicado hasta el mes anterior (el del mes en curso aún no existe)
    ultimo = aplicados - 1
    for k in range(1, ultimo + 1):
        mes = sumar_meses(base, k)
        if mes not in variaciones:
            faltan = ultimo - k + 1
            break
        factor *= 1 + variaciones[mes] / 100
        hasta = mes
    return dict(factor=factor, hasta=hasta, meses_aplicados=max(ultimo, 0) - faltan, faltan_datos=faltan,
                proximo_ajuste=sumar_meses(base, aplicados + cada))


def precio_actual(db: Session, p: Proyecto, a_fecha: date | None = None) -> dict:
    """Precio en moneda base a la fecha y descripción del contrato."""
    hoy = a_fecha or date.today()
    base = costeo.moneda_base(db)
    original = float(p.precio_base) if p.precio_base is not None else None
    if p.moneda_contrato and p.moneda_contrato != base and p.precio_contrato is not None:
        try:
            fx = costeo.base_por_unidad(db, p.moneda_contrato, hoy)
        except costeo.FaltaCotizacion:
            fx = None
        precio = round(float(p.precio_contrato) * fx, 2) if fx else original
        return dict(tipo="moneda", precio=precio, original=original, moneda=p.moneda_contrato,
                    precio_contrato=float(p.precio_contrato), cotizacion=fx,
                    texto=f"Contrato en {p.moneda_contrato}: {float(p.precio_contrato):,.2f}")
    if p.ajuste_indice == "ipc" and original and p.ajuste_mes_base:
        f = factor_ipc(db, p.ajuste_mes_base, p.ajuste_cada_meses or 1, hoy)
        return dict(tipo="ipc", precio=round(original * f["factor"], 2), original=original, moneda=base, **f)
    return dict(tipo="fijo", precio=original, original=original, moneda=base)


def factor_aumento_costos(aumento_mensual: float, desde: date, hasta: date) -> float:
    """Factor medio de aumento del trabajo pendiente entre `desde` y `hasta`.

    Se supone que el trabajo pendiente se reparte parejo en ese período: se usa el aumento a mitad
    de camino, (1 + i) ^ (meses / 2).
    """
    if not aumento_mensual or hasta <= desde:
        return 1.0
    meses = (hasta - desde).days / 30.44
    return (1 + aumento_mensual) ** (meses / 2)
