# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Registro interno de facturas y cobros.

El comprobante fiscal se emite por fuera (ARCA/AFIP u otro sistema); acá se registra número, fecha,
importe y moneda para seguir lo facturado y lo cobrado. Cada factura y cada cobro guardan la
cotización de su fecha: si una factura en dólares se cobra con otra cotización, la diferencia es la
diferencia de cambio (positiva = ganancia).
"""
from __future__ import annotations

from datetime import date

from .models import Cobro, Factura

TOLERANCIA = 0.005


def total(f: Factura) -> float:
    return round(float(f.importe_neto) + float(f.impuesto or 0), 2)


def cobrado(f: Factura, hasta: date | None = None) -> float:
    return round(sum(float(c.importe) for c in f.cobros if hasta is None or c.fecha <= hasta), 2)


def diferencia_cambio(c: Cobro) -> float:
    """En moneda base: lo cobrado a la cotización del cobro menos lo mismo a la de la factura."""
    return round(float(c.importe) * (float(c.cotizacion) - float(c.factura.cotizacion)), 2)


def estado(f: Factura, hoy: date | None = None) -> tuple[str, int | None]:
    hoy = hoy or date.today()
    if f.anulada:
        return "anulada", None
    saldo = total(f) - cobrado(f, hoy)
    if saldo <= TOLERANCIA:
        return "cobrada", None
    if f.vencimiento and f.vencimiento < hoy:
        return "vencida", (hoy - f.vencimiento).days
    return ("parcial" if cobrado(f, hoy) > 0 else "pendiente"), None


def resumen(f: Factura, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    est, dias = estado(f, hoy)
    tot = total(f)
    cob = cobrado(f, hoy)
    saldo = 0.0 if f.anulada else max(round(tot - cob, 2), 0.0)
    return dict(total=tot, cobrado=cob, saldo=saldo, saldo_base=round(saldo * float(f.cotizacion), 2),
                diferencia_cambio=round(sum(diferencia_cambio(c) for c in f.cobros if c.fecha <= hoy), 2),
                estado=est, dias_vencida=dias)
