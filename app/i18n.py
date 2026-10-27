# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Textos de los documentos para el cliente en español e inglés (se elige al exportar)."""
from __future__ import annotations

from datetime import date

IDIOMAS = ("es", "en")

_ES = dict(
    meses=["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    estados={"no iniciada": "No iniciada", "en curso": "En curso", "terminada": "Terminada", "atrasada": "Atrasada"},
    estados_proy={"en_presupuesto": "En presupuesto", "en_curso": "En curso", "pausado": "En pausa",
                  "terminado": "Terminado", "cancelado": "Cancelado"},
    otras="Otras actividades", hoy="Hoy", id_fiscal="CUIT / ID fiscal", tel="Tel.",
    cliente="Cliente", fecha="Fecha", proyecto="Proyecto", referencia="Referencia", pagina="Página",
    inicio_proy="Inicio del proyecto", fin_proy="Fin del proyecto",
    t_propuesta="Propuesta de proyecto", t_avance="Informe de avance del proyecto",
    hoja_propuesta="Propuesta", hoja_actividades="Actividades", hoja_avance="Avance",
    cronograma_prop="Cronograma propuesto: <b>{i}</b> a <b>{f}</b> · Esfuerzo estimado: <b>{h} horas</b> · "
                    "Válida hasta el <b>{v}</b>",
    esfuerzo="Esfuerzo estimado (horas)", valido="Válida hasta",
    alcance="Alcance", cronograma="Cronograma", etapa="Etapa", inicio="Inicio", fin="Fin", hito="Hito / entregable",
    horas_est="Horas est.", etapas_act="Etapas y actividades", a="a", horas_estimadas="horas estimadas",
    entregable="Entregable", inversion="Inversión", inversion_etapa="Inversión por etapa", precio="Precio",
    subtotal="Subtotal", impuesto="Impuesto", total="Total",
    nota_reparto="El precio de cada etapa es una distribución del precio total cerrado según el esfuerzo "
                 "estimado de cada etapa.",
    nota_fx="Los importes en {m} son de referencia, a 1 {m} = {v} {b} ({f}). Los importes vinculantes están en {b}.",
    condiciones="Términos y condiciones", acepta="Aceptado por (cliente)", fecha_firma="Fecha",
    en_termino="en término", atrasado="atrasado", avance_general="Avance general", plan_fecha="Planificado a la fecha",
    etapas_term="Etapas terminadas", de="de", etapas_aprob="Etapas aprobadas", etapas_aprob_cli="Etapas aprobadas por el cliente",
    fechas_proy="Fechas del proyecto", estado="Estado",
    estado_al="Estado al <b>{f}</b>: el proyecto está <b>{e}</b>.",
    proximo="Próximo hito: <b>{h}</b> ({e}), previsto para el <b>{f}</b>.", proximo_hito="Próximo hito",
    fecha_prevista="Fecha prevista",
    crono_avance="Cronograma y avance",
    leyenda="Barra clara: período previsto · relleno oscuro: avance · rombo: hito (verde = entregado) · "
            "línea punteada: hoy",
    avance_etapa="Avance por etapa", fin_previsto="Fin previsto", inicio_previsto="Inicio previsto",
    avance="Avance", planificado="Planificado", aprobada="Aprobada", entregado="Entregado", pendiente="Pendiente",
    hito_entregado="Hito entregado", fecha_aprob="Fecha de aprobación", si="Sí", no="No",
    actividades="Actividades", actividad="Actividad", fechas_previstas="Fechas previstas", hecha="Hecha",
    graf_avance="Avance vs planificado por etapa",
    nombre_propuesta="Propuesta", nombre_avance="Informe de avance",
    periodos={1: "mensual", 3: "trimestral", 6: "semestral", 12: "anual"}, cada_n_meses="cada {n} meses",
    nota_ipc="Los precios en pesos se ajustan en forma {p} por la variación del IPC (INDEC) desde {m}.",
    meses_largos=["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                  "octubre", "noviembre", "diciembre"],
    nota_fx2="Los importes en {m} son de referencia, a 1 {x} = {v} {y} ({f}). Los importes vinculantes están en {b}.",
)

_EN = dict(
    meses=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    estados={"no iniciada": "Not started", "en curso": "In progress", "terminada": "Completed",
             "atrasada": "Behind schedule"},
    estados_proy={"en_presupuesto": "Proposal", "en_curso": "In progress", "pausado": "On hold",
                  "terminado": "Completed", "cancelado": "Cancelled"},
    otras="Other activities", hoy="Today", id_fiscal="Tax ID", tel="Tel.",
    cliente="Client", fecha="Date", proyecto="Project", referencia="Reference", pagina="Page",
    inicio_proy="Project start", fin_proy="Project end",
    t_propuesta="Project Proposal", t_avance="Project Progress Report",
    hoja_propuesta="Proposal", hoja_actividades="Activities", hoja_avance="Progress",
    cronograma_prop="Proposed schedule: <b>{i}</b> to <b>{f}</b> · Estimated effort: <b>{h} hours</b> · "
                    "Valid until <b>{v}</b>",
    esfuerzo="Estimated effort (hours)", valido="Valid until",
    alcance="Scope", cronograma="Timeline", etapa="Stage", inicio="Start", fin="End", hito="Milestone",
    horas_est="Est. hours", etapas_act="Stages and activities", a="to", horas_estimadas="estimated hours",
    entregable="Deliverable", inversion="Investment", inversion_etapa="Investment by stage", precio="Price",
    subtotal="Subtotal", impuesto="Tax", total="Total",
    nota_reparto="Prices per stage are an allocation of the total fixed price according to the estimated "
                 "effort of each stage.",
    nota_fx="Amounts in {m} are for reference, at 1 {m} = {v} {b} ({f}). The binding amounts are in {b}.",
    condiciones="Terms and conditions", acepta="Accepted by (client)", fecha_firma="Date",
    en_termino="on track", atrasado="behind schedule", avance_general="Overall progress", plan_fecha="Planned to date",
    etapas_term="Stages completed", de="of", etapas_aprob="Stages approved", etapas_aprob_cli="Stages approved by client",
    fechas_proy="Project dates", estado="Status",
    estado_al="Status as of <b>{f}</b>: the project is <b>{e}</b>.",
    proximo="Next milestone: <b>{h}</b> ({e}), planned for <b>{f}</b>.", proximo_hito="Next milestone",
    fecha_prevista="Planned date",
    crono_avance="Timeline and progress",
    leyenda="Light bar: planned period · dark fill: progress · diamond: milestone (green = delivered) · "
            "dashed line: today",
    avance_etapa="Progress by stage", fin_previsto="Planned end", inicio_previsto="Planned start",
    avance="Progress", planificado="Planned", aprobada="Approved", entregado="Delivered", pendiente="Pending",
    hito_entregado="Milestone delivered", fecha_aprob="Approval date", si="Yes", no="No",
    actividades="Activities", actividad="Activity", fechas_previstas="Planned dates", hecha="Done",
    graf_avance="Progress vs planned by stage",
    nombre_propuesta="Proposal", nombre_avance="Progress report",
    periodos={1: "monthly", 3: "quarterly", 6: "every six months", 12: "yearly"}, cada_n_meses="every {n} months",
    nota_ipc="Prices in Argentine pesos are adjusted {p} by the change in the CPI (INDEC) since {m}.",
    meses_largos=["January", "February", "March", "April", "May", "June", "July", "August", "September",
                  "October", "November", "December"],
    nota_fx2="Amounts in {m} are for reference, at 1 {x} = {v} {y} ({f}). The binding amounts are in {b}.",
)

TEXTOS = {"es": _ES, "en": _EN}


def textos(idioma: str | None) -> dict:
    return TEXTOS.get((idioma or "es").lower(), _ES)


def fecha(d: date | None, t: dict) -> str:
    return f"{d.day:02d} {t['meses'][d.month - 1]} {d.year}" if d else "—"


def numero(v: float, decimales: int, idioma: str) -> str:
    """1234.5 -> '1.234,50' (es) o '1,234.50' (en)."""
    s = f"{v:,.{decimales}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") if idioma == "es" else s


def mes_anio(d: date, t: dict) -> str:
    return f"{t['meses_largos'][d.month - 1]} {d.year}"


def nota_fx(fx: dict, mon: str, t: dict, idioma: str) -> str:
    """Aclaración de la columna en otra moneda, con la cotización expresada en el sentido legible."""
    m, v = fx["moneda"], fx["valor"]
    x, y, val = (m, mon, v) if v >= 1 else (mon, m, 1 / v)
    return t["nota_fx2"].format(m=m, x=x, v=numero(val, 4 if val < 100 else 2, idioma), y=y,
                                f=fecha(fx["fecha"], t), b=mon)
