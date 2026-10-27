# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""PDF para el cliente (español o inglés): propuesta de alcance y presupuesto, o informe de avance."""
from __future__ import annotations

import io
from datetime import date, timedelta

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import i18n

TINTA = colors.HexColor("#1c2230")
GRIS = colors.HexColor("#5d6677")
LINEA = colors.HexColor("#e3e6eb")
ACENTO = colors.HexColor("#2456c8")
SUAVE = colors.HexColor("#dbe5f8")
BORDE_SUAVE = colors.HexColor("#9db5ea")
OK = colors.HexColor("#1a7f37")
ATRASO = colors.HexColor("#b26a00")
FONDO = colors.HexColor("#f5f6f8")

_ss = getSampleStyleSheet()
E = {
    "titulo": ParagraphStyle("titulo", parent=_ss["Title"], fontName="Helvetica-Bold", fontSize=20,
                             leading=24, alignment=0, textColor=TINTA, spaceAfter=2),
    "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=10, textColor=GRIS, leading=14),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, textColor=TINTA, leading=16,
                         spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, textColor=TINTA, leading=13,
                         spaceBefore=8, spaceAfter=2),
    "txt": ParagraphStyle("txt", fontName="Helvetica", fontSize=9.5, textColor=TINTA, leading=13.5),
    "chico": ParagraphStyle("chico", fontName="Helvetica", fontSize=8.5, textColor=GRIS, leading=11),
    "der": ParagraphStyle("der", fontName="Helvetica", fontSize=9, textColor=GRIS, leading=12, alignment=TA_RIGHT),
    "izq": ParagraphStyle("izq", fontName="Helvetica", fontSize=9, textColor=GRIS, leading=12),
    "celda": ParagraphStyle("celda", fontName="Helvetica", fontSize=8.8, textColor=TINTA, leading=11),
}
# Idioma del documento en curso (lo fija cada función pública antes de armar el PDF)
_T = {"t": i18n.textos("es"), "idioma": "es"}


def _usar(d: dict) -> dict:
    _T.update(t=d["t"], idioma=d["idioma"])
    return d["t"]


def f(d: date | None) -> str:
    return i18n.fecha(d, _T["t"])


def n(v: float, dec: int = 2) -> str:
    return i18n.numero(v, dec, _T["idioma"])


def dinero(v: float | None, moneda: str) -> str:
    return "—" if v is None else f"{moneda} {n(v)}"


def pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tabla(filas, anchos, num_cols=(), cabecera=True, total=False) -> Table:
    t = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0)
    st = [("FONT", (0, 0), (-1, -1), "Helvetica", 8.8), ("TEXTCOLOR", (0, 0), (-1, -1), TINTA),
          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if cabecera:
        st += [("BACKGROUND", (0, 0), (-1, 0), TINTA), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5)]
    for c in num_cols:
        st.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    if total:
        st += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9.5), ("BACKGROUND", (0, -1), (-1, -1), FONDO),
               ("LINEABOVE", (0, -1), (-1, -1), 0.8, TINTA)]
    t.setStyle(TableStyle(st))
    return t


def _cronograma(d: dict, con_avance: bool, ancho: float) -> Drawing | None:
    etapas = [e for e in d["etapas"] if e["inicio"] and e["fin"]]
    if not etapas:
        return None
    ini = min(e["inicio"] for e in etapas)
    fin = max(max(e["fin"] for e in etapas), d["fecha"] if con_avance else ini)
    ini, fin = ini - timedelta(days=1), fin + timedelta(days=2)
    total = max((fin - ini).days, 1)
    L, FILA, ARRIBA = 52 * mm, 9 * mm, 8 * mm
    alto = ARRIBA + FILA * len(etapas) + 4 * mm
    dw = Drawing(ancho, alto)
    X = lambda x: L + (x - ini).days / total * (ancho - L - 4)  # noqa: E731
    # marcas de mes
    MESES = _T["t"]["meses"]
    dw.add(String(L + 2, alto - ARRIBA + 4, f"{MESES[ini.month - 1]} {str(ini.year)[2:]}",
                  fontName="Helvetica", fontSize=7, fillColor=GRIS))
    m = date(ini.year, ini.month, 1)
    while m <= fin:
        if m > ini + timedelta(days=6):
            dw.add(Line(X(m), alto - ARRIBA + 2, X(m), 2, strokeColor=LINEA, strokeWidth=0.5))
            dw.add(String(X(m) + 2, alto - ARRIBA + 4, f"{MESES[m.month - 1]} {str(m.year)[2:]}",
                          fontName="Helvetica", fontSize=7, fillColor=GRIS))
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for i, e in enumerate(etapas):
        y = alto - ARRIBA - (i + 1) * FILA + 2.5 * mm
        nombre = e["nombre"] if len(e["nombre"]) <= 30 else e["nombre"][:29] + "…"
        dw.add(String(0, y + 1.2 * mm, nombre, fontName="Helvetica", fontSize=8, fillColor=TINTA))
        x1, x2 = X(e["inicio"]), X(e["fin"] + timedelta(days=1))
        h = 4 * mm
        dw.add(Rect(x1, y, max(x2 - x1, 1.5), h, rx=1.5, ry=1.5, fillColor=SUAVE, strokeColor=BORDE_SUAVE, strokeWidth=0.5))
        if con_avance and e["avance"]:
            col = ATRASO if e["estado_cod"] == "atrasada" else ACENTO
            dw.add(Rect(x1, y, max((x2 - x1) * min(e["avance"], 1), 0.5), h, rx=1.5, ry=1.5,
                        fillColor=col, strokeColor=None))
        if e["hito"]:
            cx, cy, r = x2, y + h / 2, 2.4 * mm
            cumplido = con_avance and e["hito_cumplido"]  # la propuesta no muestra ejecución
            dw.add(Polygon([cx, cy + r, cx + r, cy, cx, cy - r, cx - r, cy], fillColor=OK if cumplido else colors.white,
                           strokeColor=OK if cumplido else GRIS, strokeWidth=0.7))
    if con_avance and ini <= d["fecha"] <= fin:
        xh = X(d["fecha"])
        dw.add(Line(xh, alto - ARRIBA, xh, 0, strokeColor=colors.HexColor("#c62828"), strokeWidth=0.8,
                    strokeDashArray=[2, 2]))
        dw.add(String(xh + 2, 1, _T["t"]["hoy"], fontName="Helvetica-Bold", fontSize=6.5,
                      fillColor=colors.HexColor("#c62828")))
    return dw


def _encabezado(d: dict, titulo: str, ancho: float) -> list:
    emp, t = d["empresa"], d["t"]
    datos_emp = "<br/>".join([f"<b>{_esc(emp['nombre'])}</b>"] * bool(emp["nombre"]) + [_esc(x) for x in emp["lineas"]])
    # sin logo: el logo va solo en la barra de los HTML; acá van los datos de la empresa
    cab = Table([[Paragraph(datos_emp, E["izq"])]], colWidths=[ancho])
    cab.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    p = d["proyecto"]
    meta = [[t["cliente"], _esc(p["cliente"]), t["fecha"], f(d["fecha"])],
            [t["proyecto"], _esc(p["nombre"]), t["referencia"], d["referencia"]]]
    t = Table([[Paragraph(f"<font color='#5d6677'>{a}</font>", E["celda"]), Paragraph(f"<b>{b}</b>", E["celda"]),
                Paragraph(f"<font color='#5d6677'>{c}</font>", E["celda"]), Paragraph(f"<b>{dd}</b>", E["celda"])]
               for a, b, c, dd in meta], colWidths=[22 * mm, ancho * 0.5 - 22 * mm, 24 * mm, ancho * 0.5 - 24 * mm])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return [cab, Spacer(1, 8 * mm), Paragraph(titulo, E["titulo"]), Spacer(1, 3 * mm), t, Spacer(1, 4 * mm)]


def _pie(d: dict):
    def dibujar(canvas, doc):
        canvas.saveState()
        w, _ = A4
        canvas.setStrokeColor(LINEA)
        canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        izq = d["empresa"]["nombre"] or d["proyecto"]["nombre"]
        canvas.drawString(18 * mm, 9.5 * mm, f"{izq} · {d['referencia']}")
        canvas.drawRightString(w - 18 * mm, 9.5 * mm, f"{d['t']['pagina']} {doc.page}")
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawCentredString(w / 2, 5.5 * mm, d["credito"])
        canvas.restoreState()
    return dibujar


def propuesta(d: dict) -> bytes:
    """Propuesta: alcance por etapa, cronograma, actividades, horas estimadas e inversión."""
    t = _usar(d)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title=f"{t['nombre_propuesta']} - {d['proyecto']['nombre']}",
                            author=d["empresa"]["nombre"] or "")
    ancho = A4[0] - 36 * mm
    fx, mb = d["fx"], d["moneda"]
    h = _encabezado(d, t["t_propuesta"], ancho)
    p = d["proyecto"]
    h.append(Paragraph(t["cronograma_prop"].format(i=f(p["inicio"]), f=f(p["fin"]), h=n(d["horas_totales"], 0),
                                                   v=f(d["valido_hasta"])), E["txt"]))
    if p["alcance"]:
        h += [Paragraph(t["alcance"], E["h2"]), Paragraph(_esc(p["alcance"]).replace("\n", "<br/>"), E["txt"])]

    h.append(Paragraph(t["cronograma"], E["h2"]))
    cr = _cronograma(d, False, ancho)
    if cr:
        h.append(cr)
    filas = [[t["etapa"], t["inicio"], t["fin"], t["hito"], t["horas_est"]]]
    for e in d["etapas"]:
        filas.append([Paragraph(_esc(e["nombre"]), E["celda"]), f(e["inicio"]), f(e["fin"]),
                      Paragraph(_esc(e["hito"] or "—"), E["celda"]), n(e["horas"], 1)])
    h += [Spacer(1, 3 * mm), _tabla(filas, [45 * mm, 24 * mm, 24 * mm, ancho - 118 * mm, 25 * mm], num_cols=(4,))]

    h.append(Paragraph(t["etapas_act"], E["h2"]))
    for i, e in enumerate(d["etapas"], 1):
        bloque = [Paragraph(f"{i}. {_esc(e['nombre'])}", E["h3"]),
                  Paragraph(f"{f(e['inicio'])} {t['a']} {f(e['fin'])} · {n(e['horas'], 1)} {t['horas_estimadas']}"
                            + (f" · {t['entregable']}: <b>{_esc(e['hito'])}</b>" if e["hito"] else ""), E["chico"])]
        if e["tareas"]:
            filas = [[Paragraph(f"• {_esc(ta['nombre'])}", E["celda"]), f"{f(ta['inicio'])} – {f(ta['fin'])}"]
                     for ta in e["tareas"]]
            tt = Table(filas, colWidths=[ancho - 50 * mm, 50 * mm])
            tt.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 8.5), ("TEXTCOLOR", (1, 0), (1, -1), GRIS),
                                    ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (0, -1), 8)]))
            bloque.append(tt)
        h.append(KeepTogether(bloque))

    h.append(Paragraph(t["inversion"], E["h2"]))
    cab = [t["etapa"], t["horas_est"], f"{t['precio']} ({mb})"] + ([f"{t['precio']} ({fx['moneda']})"] if fx else [])
    filas = [cab]
    conv = (lambda v: dinero(v * fx["factor"], fx["moneda"])) if fx else None
    for e in d["etapas"]:
        filas.append([Paragraph(_esc(e["nombre"]), E["celda"]), n(e["horas"], 1), dinero(e["precio"], mb)]
                     + ([conv(e["precio"])] if fx else []))
    if d["impuesto_pct"]:
        filas.append([t["subtotal"], n(d["horas_totales"], 1), dinero(d["precio"], mb)] + ([conv(d["precio"])] if fx else []))
        filas.append([f"{t['impuesto']} ({n(d['impuesto_pct'] * 100)}%)", "", dinero(d["impuesto"], mb)]
                     + ([conv(d["impuesto"])] if fx else []))
    filas.append([t["total"], n(d["horas_totales"], 1), dinero(d["total"], mb)] + ([conv(d["total"])] if fx else []))
    anchos = [ancho - 105 * mm, 25 * mm, 40 * mm, 40 * mm] if fx else [ancho - 65 * mm, 25 * mm, 40 * mm]
    h.append(_tabla(filas, anchos, num_cols=tuple(range(1, len(cab))), total=True))
    notas = [t["nota_reparto"]]
    if fx:
        notas.append(i18n.nota_fx(fx, mb, t, d["idioma"]))
    if d.get("nota_ajuste"):
        notas.append(d["nota_ajuste"])
    h.append(Spacer(1, 2 * mm))
    h += [Paragraph(x, E["chico"]) for x in notas]
    if d["condiciones"]:
        h += [Paragraph(t["condiciones"], E["h2"]), Paragraph(_esc(d["condiciones"]).replace("\n", "<br/>"), E["txt"])]
    h += [Spacer(1, 10 * mm), _firmas(ancho, t)]
    doc.build(h, onFirstPage=_pie(d), onLaterPages=_pie(d))
    return buf.getvalue()


def _firmas(ancho: float, t: dict) -> Table:
    t_ = Table([["", "", ""], [t["acepta"], "", t["fecha_firma"]]], colWidths=[ancho * 0.55, ancho * 0.1, ancho * 0.35],
               rowHeights=[14 * mm, 6 * mm])
    t_.setStyle(TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.6, TINTA), ("LINEABOVE", (2, 1), (2, 1), 0.6, TINTA),
                            ("FONT", (0, 1), (-1, 1), "Helvetica", 8), ("TEXTCOLOR", (0, 1), (-1, 1), GRIS)]))
    return KeepTogether([t_])


def informe_avance(d: dict) -> bytes:
    """Informe de avance para el cliente: avance por etapa, hitos y aprobaciones (sin costos)."""
    t = _usar(d)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title=f"{t['nombre_avance']} - {d['proyecto']['nombre']}",
                            author=d["empresa"]["nombre"] or "")
    ancho = A4[0] - 36 * mm
    h = _encabezado(d, t["t_avance"], ancho)
    p = d["proyecto"]
    estado = t["en_termino"] if d["avance"] + 0.02 >= d["avance_planificado"] else t["atrasado"]
    ne = len(d["etapas"])
    resumen = [[t["avance_general"], pct(d["avance"]), t["plan_fecha"], pct(d["avance_planificado"])],
               [t["etapas_term"], f"{d['etapas_terminadas']} {t['de']} {ne}",
                t["etapas_aprob"], f"{d['etapas_aprobadas']} {t['de']} {ne}"],
               [t["fechas_proy"], f"{f(p['inicio'])} – {f(p['fin'])}", t["estado"], p["estado"]]]
    tb = Table([[Paragraph(f"<font color='#5d6677'>{a}</font>", E["celda"]), Paragraph(f"<b>{b}</b>", E["celda"]),
                 Paragraph(f"<font color='#5d6677'>{c}</font>", E["celda"]), Paragraph(f"<b>{dd}</b>", E["celda"])]
                for a, b, c, dd in resumen], colWidths=[32 * mm, ancho / 2 - 32 * mm, 32 * mm, ancho / 2 - 32 * mm])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FONDO), ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    h += [Paragraph(t["estado_al"].format(f=f(d["fecha"]), e=estado), E["txt"]), Spacer(1, 3 * mm), tb]
    if d["proximo_hito"]:
        ph = d["proximo_hito"]
        h += [Spacer(1, 3 * mm), Paragraph(t["proximo"].format(h=_esc(ph["hito"]), e=_esc(ph["etapa"]),
                                                               f=f(ph["fecha"])), E["txt"])]

    h.append(Paragraph(t["crono_avance"], E["h2"]))
    cr = _cronograma(d, True, ancho)
    if cr:
        h += [cr, Paragraph(t["leyenda"], E["chico"])]

    h.append(Paragraph(t["avance_etapa"], E["h2"]))
    filas = [[t["etapa"], t["fin_previsto"], t["avance"], t["planificado"], t["estado"], t["hito"], t["aprobada"]]]
    for e in d["etapas"]:
        filas.append([Paragraph(_esc(e["nombre"]), E["celda"]), f(e["fin"]), pct(e["avance"]),
                      pct(e["avance_planificado"]), e["estado"],
                      (t["entregado"] + " " + f(e["hito_cumplido"])) if e["hito_cumplido"] else (t["pendiente"] if e["hito"] else "—"),
                      f(e["fecha_aprobacion"]) if e["aprobada"] else t["pendiente"]])
    tb = _tabla(filas, [34 * mm, 22 * mm, 17 * mm, 17 * mm, 25 * mm, 34 * mm, ancho - 149 * mm], num_cols=(2, 3))
    estilos = []
    for i, e in enumerate(d["etapas"], 1):
        if e["estado_cod"] == "atrasada":
            estilos.append(("TEXTCOLOR", (4, i), (4, i), ATRASO))
        elif e["estado_cod"] == "terminada":
            estilos.append(("TEXTCOLOR", (4, i), (4, i), OK))
    tb.setStyle(TableStyle(estilos))
    h.append(tb)

    h.append(Paragraph(t["actividades"], E["h2"]))
    for e in d["etapas"]:
        if not e["tareas"]:
            continue
        filas = [[Paragraph(_esc(ta["nombre"]), E["celda"]), f"{f(ta['inicio'])} – {f(ta['fin'])}",
                  t["hecha"] if ta["terminada"] else pct(ta["avance"])] for ta in e["tareas"]]
        tt = _tabla([[t["actividad"], t["fechas_previstas"], t["avance"]]] + filas,
                    [ancho - 75 * mm, 50 * mm, 25 * mm], num_cols=(2,))
        h.append(KeepTogether([Paragraph(_esc(e["nombre"]), E["h3"]), tt]))
    doc.build(h, onFirstPage=_pie(d), onLaterPages=_pie(d))
    return buf.getvalue()
