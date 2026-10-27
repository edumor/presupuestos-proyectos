# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Tableros de rentabilidad por período y su exportación a Excel."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import CREDITO, excel, rentabilidad
from ..database import get_db
from ..excel import FMT_NUM, FMT_PCT, fmt_moneda
from .exportar import _descarga

router = APIRouter(prefix="/api", tags=["Rentabilidad"])
ESTADOS_FACT = {"pendiente": "Pendiente", "parcial": "Cobro parcial", "vencida": "Vencida", "cobrada": "Cobrada",
                "anulada": "Anulada"}


def _periodo(desde: date | None, hasta: date | None) -> tuple[date, date]:
    hoy = date.today()
    hasta = hasta or hoy
    desde = desde or date(hasta.year, 1, 1)
    if desde > hasta:
        raise HTTPException(422, "La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days > 366 * 5:
        raise HTTPException(422, "El período no puede superar 5 años")
    return desde, hasta


@router.get("/rentabilidad")
def tablero(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    d, h = _periodo(desde, hasta)
    return rentabilidad.calcular(db, d, h)


@router.get("/export/rentabilidad")
def exportar(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    d, h = _periodo(desde, hasta)
    r = rentabilidad.calcular(db, d, h)
    m = fmt_moneda(r["moneda"])
    t = r["totales"]
    wb = excel.libro()

    ws = wb.create_sheet("Resumen")
    ws.cell(1, 1, "Rentabilidad del período").font = excel.Font(bold=True, size=14)
    fila = excel.ficha(ws, 3, [
        ("Desde", d, None), ("Hasta", h, None), ("Moneda", r["moneda"], None),
        ("Ingreso devengado (por avance)", t["devengado"], m), ("Costo (horas + gastos)", t["costo"], m),
        ("Margen", t["margen"], m), ("Margen %", t["margen_pct"], FMT_PCT),
        ("Facturado (neto)", t["facturado"], m), ("Cobrado", t["cobrado"], m),
        ("Diferencia de cambio en cobros", t["diferencia_cambio"], m),
        ("Saldo a cobrar al cierre", t["saldo_a_cobrar"], m), ("Vencido", t["vencido"], m),
        ("Horas cargadas", t["horas"], FMT_NUM)])
    ws.cell(fila + 1, 1, "Ingreso devengado = precio vigente × avance ganado en el período. "
                         "Costo = horas cargadas × costo por hora (con estructura) + gastos externos reales.")
    ws.cell(fila + 3, 1, CREDITO).font = excel.Font(color="5D6677", size=9)

    cols = [("Proyecto", None), ("Cliente", None), ("Avance inicio", FMT_PCT), ("Avance cierre", FMT_PCT),
            ("Devengado", m), ("Costo horas", m), ("Gastos", m), ("Costo", m), ("Margen", m), ("Margen %", FMT_PCT),
            ("Facturado", m), ("Cobrado", m), ("Dif. de cambio", m), ("Saldo a cobrar", m)]
    ws = excel.hoja_datos(wb, "Proyectos", cols, [
        [x["proyecto"], x["cliente"], x["avance_inicio"], x["avance_fin"], x["devengado"], x["costo_horas"],
         x["costo_gastos"], x["costo"], x["margen"], x["margen_pct"], x["facturado"], x["cobrado"],
         x["diferencia_cambio"], x["saldo_a_cobrar"]] for x in r["proyectos"]])

    cols = [("Cliente", None), ("Proyectos", "0"), ("Devengado", m), ("Costo", m), ("Margen", m),
            ("Margen %", FMT_PCT), ("Facturado", m), ("Cobrado", m), ("Saldo a cobrar", m)]
    datos = [[x["cliente"], x["proyectos"], x["devengado"], x["costo"], x["margen"], x["margen_pct"],
              x["facturado"], x["cobrado"], x["saldo_a_cobrar"]] for x in r["clientes"]]
    ws = excel.hoja_datos(wb, "Clientes", cols, datos)
    if datos:
        excel.grafico_barras(ws, "Margen por cliente", 1, len(datos) + 1, 1, [5], "K2", horizontal=True)

    cols = [("Servicio", None), ("Tareas", "0"), ("Horas previstas", FMT_NUM), ("Horas previstas p/ avance", FMT_NUM),
            ("Horas reales", FMT_NUM), ("Desvío horas", FMT_PCT), ("Costo previsto", m), ("Costo real", m),
            ("Desvío costo", FMT_PCT)]
    datos = [[x["servicio"], x["tareas"], x["horas_previstas"], x["horas_ganadas"], x["horas_reales"],
              x["desvio_horas"], x["costo_previsto"], x["costo_real"], x["desvio_costo"]] for x in r["servicios"]]
    ws = excel.hoja_datos(wb, "Servicios", cols, datos)
    if datos:
        excel.grafico_barras(ws, "Horas previstas para el avance vs reales", 1, len(datos) + 1, 1, [4, 5], "K2",
                             horizontal=True)

    cols = [("Persona", None), ("Tipo", None), ("Rol", None), ("Proyectos", "0"), ("Horas", FMT_NUM),
            ("Horas disponibles", FMT_NUM), ("Utilización", FMT_PCT), ("Horas objetivo", FMT_NUM),
            ("Cumplimiento objetivo", FMT_PCT), ("Costo", m), ("Valor vendido", m), ("Margen", m), ("Margen %", FMT_PCT)]
    excel.hoja_datos(wb, "Personas", cols, [
        [x["persona"], x["tipo"], x["rol"], x["proyectos"], x["horas"], x["horas_disponibles"], x["utilizacion"],
         x["horas_objetivo"], x["cumplimiento_objetivo"], x["costo"], x["valor"], x["margen"], x["margen_pct"]]
        for x in r["personas"]])

    cols = [("Mes", "mm/yyyy"), ("Facturado (con impuestos)", m), ("Cobrado", m), ("Costos", m), ("Neto", m),
            ("Acumulado", m), ("Dif. de cambio", m)]
    datos = [[x["mes"], x["facturado"], x["cobrado"], x["costos"], x["neto"], x["acumulado"], x["diferencia_cambio"]]
             for x in r["flujo"]]
    ws = excel.hoja_datos(wb, "Flujo de caja", cols, datos)
    if datos:
        excel.grafico_barras(ws, "Cobrado vs costos por mes", 1, len(datos) + 1, 1, [3, 4], "I2")

    cols = [("Número", None), ("Cliente", None), ("Proyecto", None), ("Fecha", None), ("Vencimiento", None),
            ("Moneda", None), ("Saldo", FMT_NUM), (f"Saldo {r['moneda']}", m), ("Estado", None), ("Días vencida", "0")]
    excel.hoja_datos(wb, "A cobrar", cols, [
        [x["numero"], x["cliente"], x["proyecto"], x["fecha"], x["vencimiento"], x["moneda"], x["saldo"],
         x["saldo_base"], ESTADOS_FACT.get(x["estado"], x["estado"]), x["dias_vencida"]] for x in r["a_cobrar"]])
    return _descarga(excel.a_bytes(wb), f"Rentabilidad {d:%Y%m%d}-{h:%Y%m%d}")
