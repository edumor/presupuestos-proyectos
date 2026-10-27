# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Descargas en Excel: proyecto completo, cartera y base completa."""
import re
import unicodedata
from urllib.parse import quote
from datetime import date

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import CREDITO, costeo, dashboard_html, documentos, excel, excel_cliente, pdf_cliente, seguimiento
from ..database import Base, get_db
from ..excel import FMT_NUM, FMT_PCT, fmt_moneda
from ..models import CostoExterno, Presupuesto, Proyecto
from ..schemas import MONEDAS

router = APIRouter(prefix="/api/export", tags=["Exportar"])
ESTADOS = {"en_presupuesto": "En presupuesto", "en_curso": "En curso", "pausado": "Pausado",
           "terminado": "Terminado", "cancelado": "Cancelado"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


MIME = {"xlsx": XLSX, "pdf": "application/pdf", "html": "text/html; charset=utf-8"}


def _descarga(contenido: bytes, nombre: str, ext: str = "xlsx") -> Response:
    limpio = re.sub(r"[^\w\- ]", "", nombre).strip().replace(" ", "_") or "export"
    archivo = f"{limpio}_{date.today():%Y%m%d}.{ext}"
    ascii_ = unicodedata.normalize("NFKD", archivo).encode("ascii", "ignore").decode()
    return Response(contenido, media_type=MIME[ext], headers={
        "Content-Disposition": f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(archivo)}"})


@router.get("/proyecto/{pid}")
def proyecto(pid: int, db: Session = Depends(get_db)):
    p = db.get(Proyecto, pid)
    if p is None:
        raise HTTPException(404, "Proyecto inexistente")
    hoy = date.today()
    m = seguimiento.metricas(db, p, hoy)
    mb = costeo.moneda_base(db)
    FB = fmt_moneda(mb)
    wb = excel.libro()

    # Resumen
    ws = wb.create_sheet("Resumen")
    ws.cell(1, 1, p.nombre).font = excel.Font(bold=True, size=14)
    ws.cell(2, 1, f"Cliente: {m['cliente']} · Estado: {ESTADOS.get(m['estado'], m['estado'])} · Datos al {hoy:%d/%m/%Y}")
    f = excel.ficha(ws, 4, [
        ("Inicio previsto", p.fecha_inicio, None), ("Fin previsto", p.fecha_fin, None),
        ("Precio acordado", m["precio_base"], FB), ("Costo previsto (BAC + externos)", m["costo_previsto"], FB),
        ("Costo final estimado (EAC)", m["eac"], FB), ("Margen previsto", m["margen_previsto"], FMT_PCT),
        ("Margen proyectado", m["margen_proyectado"], FMT_PCT), ("Avance ponderado por etapas", m["avance_ponderado"], FMT_PCT),
        ("Avance planificado a hoy", m["avance_planificado"], FMT_PCT),
        ("Valor planificado (PV)", m["pv"], FB), ("Valor ganado (EV)", m["ev"], FB),
        ("Costo real mano de obra (AC)", m["ac"], FB), ("CPI (eficiencia en costo)", m["cpi"], "0.00"),
        ("SPI (eficiencia en plazo)", m["spi"], "0.00"), ("Horas previstas", m["horas_previstas"], FMT_NUM),
        ("Horas reales", m["horas_reales"], FMT_NUM), ("Gastos externos previstos", m["externos_previstos"], FB),
        ("Gastos externos reales", m["externos_reales"], FB),
    ])
    ws.cell(f + 1, 1, "CPI o SPI menores que 1 indican sobrecosto o atraso.").font = excel.Font(italic=True, color="5D6677")
    ws.cell(f + 3, 1, CREDITO).font = excel.Font(italic=True, size=8, color="8A93A3")

    # Etapas
    cols = [("Etapa", None), ("Peso", FMT_PCT), ("Inicio previsto", None), ("Fin previsto", None),
            ("Inicio real", None), ("Fin real", None), ("Avance", FMT_PCT), ("Avance planificado", FMT_PCT),
            ("Estado", None), ("Costo previsto", FB), ("Valor ganado", FB), ("Costo real", FB),
            ("Hito", None), ("Hito cumplido", None), ("Aprobada por cliente", None), ("Fecha aprobación", None)]
    datos = [[e["nombre"], e["peso_efectivo"], e["inicio_previsto"], e["fin_previsto"], e["inicio_real"], e["fin_real"],
              e["avance"], e["avance_planificado"], e["estado"], e["costo_previsto"], e["ev"], e["ac"], e["hito"],
              e["hito_cumplido"], "Sí" if e["aprobada_cliente"] else "No", e["fecha_aprobacion"]] for e in m["etapas"]]
    ws_e = excel.hoja_datos(wb, "Etapas", cols, datos)
    if datos:
        excel.grafico_barras(ws_e, "Avance real vs planificado por etapa", 1, len(datos) + 1, 1, [7, 8],
                             f"A{len(datos) + 4}", horizontal=True, eje_y="%")

    # Tareas
    etapas = {e.id: e.nombre for e in p.etapas}
    cols = [("Etapa", None), ("Tarea", None), ("Responsable", None), ("Inicio previsto", None), ("Fin previsto", None),
            ("Inicio real", None), ("Fin real", None), ("Horas previstas", FMT_NUM), ("Horas reales", FMT_NUM),
            ("Costo hora", FB), ("Costo previsto", FB), ("Costo real", FB), ("Avance", FMT_PCT)]
    datos = []
    for t in sorted(p.tareas, key=lambda t: (t.fecha_inicio, t.orden)):
        hr = sum(h.horas for h in t.horas)
        cr = sum(h.horas * float(h.costo_hora_base) for h in t.horas)
        datos.append([etapas.get(t.etapa_id, "Sin etapa"), t.nombre, t.persona.nombre if t.persona else None,
                      t.fecha_inicio, t.fecha_fin, t.inicio_real, t.fin_real, t.horas_previstas, hr,
                      t.costo_hora_base, t.costo_previsto_base, cr, seguimiento.avance_tarea(t, hoy)])
    excel.hoja_datos(wb, "Tareas", cols, datos)

    # Horas
    cols = [("Fecha", None), ("Persona", None), ("Tarea", None), ("Horas", FMT_NUM), ("Costo hora", FB),
            ("Costo", FB), ("Nota", None)]
    datos = sorted(([h.fecha, t.persona.nombre if t.persona and t.persona_id == h.persona_id else h.persona_id,
                     t.nombre, h.horas, h.costo_hora_base, h.horas * float(h.costo_hora_base), h.nota]
                    for t in p.tareas for h in t.horas), key=lambda r: r[0])
    from ..models import Persona
    nombres = {x.id: x.nombre for x in db.scalars(select(Persona))}
    for r in datos:
        if isinstance(r[1], int):
            r[1] = nombres.get(r[1], r[1])
    excel.hoja_datos(wb, "Horas", cols, datos)

    # Gastos
    gs = db.scalars(select(CostoExterno).where(CostoExterno.proyecto_id == pid)).all()
    cols = [("Concepto", None), ("Tipo", None), ("Fecha", None), ("Moneda", None), ("Importe", FMT_NUM),
            (f"Cotización ({mb} por unidad)", "#,##0.0000"), (f"Importe {mb}", FB)]
    excel.hoja_datos(wb, "Gastos", cols, [[g.concepto, "Real" if g.es_real else "Previsto", g.fecha, g.moneda,
                                            g.importe, g.cotizacion, g.importe_base] for g in gs])

    # Curva S
    serie = seguimiento.curva_s(db, p, hoy)
    cols = [("Fecha", None), ("Valor planificado (PV)", FB), ("Valor ganado (EV)", FB), ("Costo real (AC)", FB)]
    ws_c = excel.hoja_datos(wb, "Curva S", cols, [[s["fecha"], s["pv"], s["ev"], s["ac"]] for s in serie], filtro=False)
    if serie:
        excel.grafico_lineas(ws_c, "Curva S: planificado, ganado y real", 1, len(serie) + 1, 1, [2, 3, 4], "F2", eje_y=mb)

    # Por persona
    pp = seguimiento.costo_por_persona(p, hoy)
    cols = [("Persona", None), ("Horas previstas", FMT_NUM), ("Horas reales", FMT_NUM),
            ("Costo previsto", FB), ("Costo real", FB)]
    ws_p = excel.hoja_datos(wb, "Por persona", cols, [[x["nombre"], x["horas_previstas"], x["horas_reales"],
                                                       x["costo_previsto"], x["costo_real"]] for x in pp])
    if pp:
        excel.grafico_barras(ws_p, "Costo previsto vs real por persona", 1, len(pp) + 1, 1, [4, 5], "G2", horizontal=True, eje_y=mb)
    return _descarga(excel.a_bytes(wb), p.nombre)


@router.get("/cartera")
def cartera(incluir_terminados: bool = True, db: Session = Depends(get_db)):
    proys = db.scalars(select(Proyecto).order_by(Proyecto.fecha_inicio)).all() if incluir_terminados \
        else seguimiento.proyectos_activos(db)
    mb = costeo.moneda_base(db)
    FB = fmt_moneda(mb)
    wb = excel.libro()
    cols = [("Proyecto", None), ("Cliente", None), ("Estado", None), ("Inicio", None), ("Fin", None),
            ("Precio", FB), ("Costo previsto", FB), ("Costo final estimado", FB),
            ("Margen previsto", FMT_PCT), ("Margen proyectado", FMT_PCT), ("Avance ponderado", FMT_PCT),
            ("Avance planificado", FMT_PCT), ("CPI", "0.00"), ("SPI", "0.00"), ("Etapas atrasadas", "0"),
            ("Próximo hito", None), ("Fecha próximo hito", None)]
    datos = []
    for p in proys:
        m = seguimiento.metricas(db, p)
        h = m["proximo_hito"] or {}
        datos.append([p.nombre, m["cliente"], ESTADOS.get(m["estado"], m["estado"]), p.fecha_inicio, p.fecha_fin, m["precio_base"],
                      m["costo_previsto"], m["eac"], m["margen_previsto"], m["margen_proyectado"],
                      m["avance_ponderado"], m["avance_planificado"], m["cpi"], m["spi"], m["etapas_atrasadas"],
                      h.get("hito"), h.get("fecha")])
    ws = excel.hoja_datos(wb, "Cartera", cols, datos)
    if datos:
        excel.grafico_barras(ws, "Margen previsto vs proyectado", 1, len(datos) + 1, 1, [9, 10],
                             f"A{len(datos) + 4}", eje_y="%")
        excel.grafico_barras(ws, "Avance real vs planificado", 1, len(datos) + 1, 1, [11, 12],
                             f"K{len(datos) + 4}", eje_y="%")
    return _descarga(excel.a_bytes(wb), "Cartera_de_proyectos")


@router.get("/base")
def base(db: Session = Depends(get_db)):
    """Todas las tablas, una hoja por tabla (respaldo legible / análisis propio)."""
    wb = excel.libro()
    for t in Base.metadata.sorted_tables:
        filas = db.execute(t.select()).all()
        cols = [(c.name, None) for c in t.columns]
        excel.hoja_datos(wb, t.name, cols, [list(f) for f in filas])
    return _descarga(excel.a_bytes(wb), "Base_completa")


def _proyecto(db: Session, pid: int) -> Proyecto:
    p = db.get(Proyecto, pid)
    if p is None:
        raise HTTPException(404, "Proyecto inexistente")
    return p


@router.get("/cliente/{pid}")
def cliente(pid: int, tipo: Literal["propuesta", "avance"] = "propuesta",
            formato: Literal["pdf", "xlsx"] = "pdf", moneda: str = "", idioma: Literal["es", "en"] = "es",
            fecha: date | None = None, db: Session = Depends(get_db)):
    """Documento para el cliente (español o inglés), sin costos internos: propuesta o informe de avance.
    `moneda`: muestra también los importes convertidos a esa moneda (p. ej. USD)."""
    p = _proyecto(db, pid)
    moneda = moneda.upper().strip()
    if moneda and moneda not in MONEDAS:
        raise HTTPException(422, "Moneda no admitida")
    d = documentos.datos(db, p, fecha, moneda or None, idioma)
    if tipo == "propuesta":
        contenido = pdf_cliente.propuesta(d) if formato == "pdf" else excel_cliente.propuesta(d)
        nombre = f"{d['t']['nombre_propuesta']} {p.nombre}"
    else:
        contenido = pdf_cliente.informe_avance(d) if formato == "pdf" else excel_cliente.informe_avance(d)
        nombre = f"{d['t']['nombre_avance']} {p.nombre}"
    return _descarga(contenido, nombre, formato)


@router.get("/dashboard/{pid}")
def dashboard(pid: int, version: Literal["interno", "cliente"] = "interno", fecha: date | None = None,
              idioma: Literal["es", "en"] = "es", db: Session = Depends(get_db)):
    """Dashboard interactivo en un único archivo HTML (se abre sin el programa ni internet).
    La versión para el cliente sale en el idioma elegido; la interna, en español."""
    p = _proyecto(db, pid)
    html = dashboard_html.generar(db, p, version, fecha, idioma)
    if version == "cliente":
        nombre = f"{'Dashboard' if idioma == 'en' else 'Tablero'} {p.nombre}"
    else:
        nombre = f"Tablero interno {p.nombre}"
    return _descarga(html.encode("utf-8"), nombre, "html")


@router.get("/presupuesto/{prid}")
def presupuesto(prid: int, formato: Literal["pdf", "xlsx"] = "pdf", moneda: str = "",
                idioma: Literal["es", "en"] = "es", fecha: date | None = None, db: Session = Depends(get_db)):
    """Propuesta para el cliente armada desde una versión del presupuesto (sin costos internos)."""
    pres = db.get(Presupuesto, prid)
    if pres is None:
        raise HTTPException(404, "Presupuesto inexistente")
    moneda = moneda.upper().strip()
    if moneda and moneda not in MONEDAS:
        raise HTTPException(422, "Moneda no admitida")
    d = documentos.datos_presupuesto(db, pres, fecha, moneda or None, idioma)
    contenido = pdf_cliente.propuesta(d) if formato == "pdf" else excel_cliente.propuesta(d)
    return _descarga(contenido, f"{d['t']['nombre_propuesta']} {pres.proyecto.nombre} v{pres.version}", formato)
