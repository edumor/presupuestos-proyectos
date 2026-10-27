# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Consulta opcional a la API pública del Banco Central de la República Argentina.

Solo se usa cuando la persona aprieta el botón correspondiente: el programa no envía datos, solo
pide cotizaciones e índices públicos.

- Cotizaciones: https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones?fecha=AAAA-MM-DD
  (tipoCotizacion = pesos por 1 unidad de la moneda).
- Inflación mensual (IPC INDEC, % mensual): https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{id}
"""
from __future__ import annotations

import json
from datetime import date

from . import red

API = "https://api.bcra.gob.ar"
ID_INFLACION_MENSUAL = 27  # "Inflación mensual." en Principales variables v4.0


class ErrorBCRA(Exception):
    pass


def _get_json(url: str) -> dict:
    try:
        return red.obtener_json(url)
    except red.ErrorHTTP as e:
        try:
            msg = "; ".join(json.loads(e.cuerpo.decode("utf-8")).get("errorMessages", [])) or f"error {e.status}"
        except Exception:
            msg = f"error {e.status}"
        raise ErrorBCRA(f"El BCRA respondió: {msg}") from e
    except red.ErrorRed as e:
        raise ErrorBCRA(f"No se pudo conectar con el BCRA ({e}). Probá de nuevo en unos minutos o cargá el "
                        "dato a mano; si sigue pasando, mirá la sección «Problemas frecuentes» del manual.") from e


def cotizaciones(fecha: date | None = None) -> tuple[date, dict[str, float]]:
    """Pesos por unidad de cada moneda en la fecha (o la última publicada si no hay dato ese día)."""
    url = f"{API}/estadisticascambiarias/v1.0/Cotizaciones" + (f"?fecha={fecha:%Y-%m-%d}" if fecha else "")
    res = _get_json(url).get("results") or {}
    if not res.get("fecha") or not res.get("detalle"):
        raise ErrorBCRA("El BCRA no publicó cotizaciones para esa fecha (fin de semana o feriado). Probá con otra.")
    valores = {d["codigoMoneda"]: float(d["tipoCotizacion"]) for d in res["detalle"] if d.get("tipoCotizacion")}
    valores["ARS"] = 1.0
    return date.fromisoformat(res["fecha"][:10]), valores


def inflacion_mensual(desde: date, hasta: date | None = None) -> dict[date, float]:
    """Variación % mensual del IPC por mes (clave: primer día del mes)."""
    hasta = hasta or date.today()
    url = (f"{API}/estadisticas/v4.0/monetarias/{ID_INFLACION_MENSUAL}"
           f"?desde={desde:%Y-%m-%d}&hasta={hasta:%Y-%m-%d}&limit=3000")
    res = _get_json(url).get("results") or []
    detalle = res[0].get("detalle", []) if res else []
    if not detalle:
        raise ErrorBCRA("El BCRA no devolvió datos de inflación para ese período.")
    return {date.fromisoformat(x["fecha"][:10]).replace(day=1): float(x["valor"]) for x in detalle}
