# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Seguimiento de proyectos: avance ponderado por etapas, valor ganado y curva S.

Definiciones (ver documento de diseño, sección "Seguimiento"):
- Avance de una tarea: el % cargado a mano; si no hay, horas reales ÷ horas previstas (tope 100%).
- PV/EV/AC se calculan sobre el costo previsto de las tareas (BAC de mano de obra).
- AC de mano de obra = Σ horas reales × costo hora de la persona a la fecha de carga.
- Los gastos externos se comparan aparte (previstos vs reales) y suman al costo final estimado.
- Avance ponderado del proyecto = Σ peso de la etapa × avance de la etapa. Si alguna etapa no tiene
  peso, todas se ponderan por su costo previsto.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import calculos, costeo
from .models import (AvanceRegistro, CostoExterno, Etapa, EstadoProyecto, HoraReal, PlantillaEtapa,
                     Proyecto, Tarea)

PLANTILLA_DEFECTO = [  # nombre, peso, % duración, hito
    ("Inicio", 0.10, 0.10, "Kick-off y brief aprobados"),
    ("Planificación", 0.20, 0.20, "Plan y calendario aprobados"),
    ("Ejecución", 0.55, 0.55, "Entregables producidos"),
    ("Cierre", 0.15, 0.15, "Informe final entregado"),
]


def asegurar_plantilla(db: Session) -> None:
    if db.scalars(select(PlantillaEtapa)).first() is None:
        for i, (n, peso, dur, hito) in enumerate(PLANTILLA_DEFECTO):
            db.add(PlantillaEtapa(nombre=n, orden=i, peso=peso, pct_duracion=dur, hito=hito))
        db.commit()


def etapas_desde_plantilla(db: Session, proyecto: Proyecto) -> list[Etapa]:
    plantilla = db.scalars(select(PlantillaEtapa).order_by(PlantillaEtapa.orden)).all()
    etapas, cursor = [], proyecto.fecha_inicio
    total = (proyecto.fecha_fin - proyecto.fecha_inicio).days if proyecto.fecha_inicio and proyecto.fecha_fin else None
    for i, p in enumerate(plantilla):
        ini = fin = None
        if total is not None and total > 0:
            ini = cursor
            if i == len(plantilla) - 1:
                fin = proyecto.fecha_fin
            else:
                fin = min(cursor + timedelta(days=max(round(total * (p.pct_duracion or 0)), 1) - 1), proyecto.fecha_fin)
            cursor = min(fin + timedelta(days=1), proyecto.fecha_fin)
        etapas.append(Etapa(nombre=p.nombre, orden=p.orden, peso=p.peso, hito=p.hito,
                            inicio_previsto=ini, fin_previsto=fin))
    return etapas


# ---------- avance por tarea ----------

def _horas_y_costo(tarea: Tarea, hasta: date) -> tuple[float, float]:
    hs = [h for h in tarea.horas if h.fecha <= hasta]
    return sum(h.horas for h in hs), sum(h.horas * float(h.costo_hora_base) for h in hs)


def avance_tarea(tarea: Tarea, a_fecha: date) -> float:
    """% de avance a una fecha.

    Hoy (o después): el % manual vigente; si está vacío, el sugerido por horas.
    Fechas pasadas: el último registro manual hasta esa fecha; si no hay, el sugerido por horas.
    """
    horas, _ = _horas_y_costo(tarea, a_fecha)
    sugerido = calculos.avance_sugerido(horas, tarea.horas_previstas)
    if a_fecha >= date.today():
        return tarea.avance if tarea.avance is not None else sugerido
    regs = [r for r in tarea.avances if r.fecha <= a_fecha]
    return regs[-1].avance if regs else sugerido


def registrar_avance(db: Session, tarea: Tarea, avance: float | None, fecha: date | None = None) -> None:
    tarea.avance = avance
    if avance is None:
        return
    fecha = fecha or date.today()
    reg = next((r for r in tarea.avances if r.fecha == fecha), None)
    if reg:
        reg.avance = avance
    else:
        tarea.avances.append(AvanceRegistro(fecha=fecha, avance=avance))


# ---------- métricas ----------

def _estado_etapa(e: Etapa | None, avance: float, hoy: date) -> str:
    if avance >= 0.999 or (e and e.fin_real):
        return "terminada"
    if e and e.fin_previsto and e.fin_previsto < hoy:
        return "atrasada"
    if avance > 0 or (e and e.inicio_real):
        return "en curso"
    return "no iniciada"


def _pv_ev_ac(tareas: list[Tarea], f: date) -> tuple[float, float, float, float]:
    pv = ev = ac = bac = 0.0
    for t in tareas:
        costo = float(t.costo_previsto_base)
        bac += costo
        # todo se mide al cierre del día f (incluye las horas cargadas ese día)
        pv += costo * calculos.avance_planificado(t.fecha_inicio, t.fecha_fin + timedelta(days=1), f + timedelta(days=1))
        ev += costo * avance_tarea(t, f)
        ac += _horas_y_costo(t, f)[1]
    return bac, pv, ev, ac


def gastos(db: Session, proyecto_id: int, hasta: date | None = None) -> tuple[float, float]:
    rows = db.scalars(select(CostoExterno).where(CostoExterno.proyecto_id == proyecto_id)).all()
    previstos = sum(float(g.importe_base) for g in rows if not g.es_real)
    reales = sum(float(g.importe_base) for g in rows if g.es_real and (hasta is None or g.fecha is None or g.fecha <= hasta))
    return previstos, reales


def metricas(db: Session, p: Proyecto, a_fecha: date | None = None) -> dict:
    hoy = a_fecha or date.today()
    tareas = p.tareas
    bac, pv, ev, ac = _pv_ev_ac(tareas, hoy)
    ext_prev, ext_real = gastos(db, p.id, hoy)
    cpi = ev / ac if ac else None
    spi = ev / pv if pv else None
    eac_mo = bac / cpi if cpi else bac
    # trabajo pendiente proyectado con el aumento previsto de sueldos y tarifas
    from . import contratos
    aumento = getattr(costeo.config(db), "aumento_costos_mensual", 0) or 0
    fin = max(p.fecha_fin or hoy, hoy)
    pendiente = max(eac_mo - ac, 0.0)
    factor_aum = contratos.factor_aumento_costos(aumento, hoy, fin)
    eac_mo_aj = ac + pendiente * factor_aum
    eac = eac_mo_aj + max(ext_prev, ext_real)
    costo_previsto = bac + ext_prev
    contrato = contratos.precio_actual(db, p, hoy)
    precio = contrato["precio"] or None
    margen_prev = (precio - costo_previsto) / precio if precio else None
    margen_proy = (precio - eac) / precio if precio else None

    # etapas
    grupos: dict[int | None, list[Tarea]] = defaultdict(list)
    for t in tareas:
        grupos[t.etapa_id].append(t)
    filas = []
    for e in p.etapas + ([None] if grupos.get(None) else []):
        ts = grupos.get(e.id if e else None, [])
        b, v, g, a = _pv_ev_ac(ts, hoy)
        if b:
            av = g / b
        elif ts:
            av = sum(avance_tarea(t, hoy) for t in ts) / len(ts)
        else:
            av = 1.0 if (e and e.fin_real) else 0.0
        filas.append(dict(
            id=e.id if e else None, nombre=e.nombre if e else "Sin etapa", orden=e.orden if e else 999,
            peso=e.peso if e else None, costo_previsto=b, pv=v, ev=g, ac=a, avance=av,
            avance_planificado=(v / b if b else None),
            inicio_previsto=e.inicio_previsto if e else None, fin_previsto=e.fin_previsto if e else None,
            inicio_real=e.inicio_real if e else None, fin_real=e.fin_real if e else None,
            hito=e.hito if e else None, hito_cumplido=e.hito_cumplido if e else None,
            aprobada_cliente=e.aprobada_cliente if e else False,
            fecha_aprobacion=e.fecha_aprobacion if e else None, notas=e.notas if e else None,
            estado=_estado_etapa(e, av, hoy), tareas=len(ts)))
    con_peso = [f for f in filas if f["id"] is not None]
    if con_peso and all(f["peso"] for f in con_peso) and not grupos.get(None):
        tot = sum(f["peso"] for f in con_peso)
        for f in filas:
            f["peso_efectivo"] = f["peso"] / tot
    else:
        tot = sum(f["costo_previsto"] for f in filas)
        for f in filas:
            f["peso_efectivo"] = f["costo_previsto"] / tot if tot else 1 / max(len(filas), 1)
    avance_pond = sum(f["peso_efectivo"] * f["avance"] for f in filas)
    proximo_hito = next((f for f in sorted(filas, key=lambda x: x["orden"]) if f["hito"] and not f["hito_cumplido"]), None)

    return dict(
        proyecto_id=p.id, nombre=p.nombre, cliente=p.cliente.nombre if p.cliente else None,
        estado=p.estado.value, fecha_inicio=p.fecha_inicio, fecha_fin=p.fecha_fin, a_fecha=hoy,
        precio_base=precio, precio_original=contrato["original"], contrato=contrato,
        aumento_costos_mensual=aumento, eac_sin_aumentos=eac_mo + max(ext_prev, ext_real), bac=bac, pv=pv, ev=ev, ac=ac, cpi=cpi, spi=spi,
        eac_mano_obra=eac_mo, externos_previstos=ext_prev, externos_reales=ext_real,
        costo_previsto=costo_previsto, eac=eac, margen_previsto=margen_prev, margen_proyectado=margen_proy,
        avance_ponderado=avance_pond, avance_costo=(ev / bac if bac else 0.0),
        avance_planificado=(pv / bac if bac else 0.0),
        horas_previstas=sum(t.horas_previstas for t in tareas),
        horas_reales=sum(_horas_y_costo(t, hoy)[0] for t in tareas),
        etapas=filas, etapas_atrasadas=sum(1 for f in filas if f["estado"] == "atrasada"),
        proximo_hito=(dict(etapa=proximo_hito["nombre"], hito=proximo_hito["hito"],
                           fecha=proximo_hito["fin_previsto"]) if proximo_hito else None),
    )


def curva_s(db: Session, p: Proyecto, hasta: date | None = None) -> list[dict]:
    """Serie semanal acumulada de PV, EV y AC (EV y AC solo hasta hoy)."""
    if not p.tareas:
        return []
    hoy = hasta or date.today()
    ini = min(t.fecha_inicio for t in p.tareas)
    fin = max(t.fecha_fin for t in p.tareas)
    fechas, f = [], ini
    while f < fin:
        fechas.append(f)
        f += timedelta(days=7)
    fechas.append(fin)
    if ini <= hoy <= fin and hoy not in fechas:
        fechas = sorted(fechas + [hoy])
    serie = []
    for f in fechas:
        bac, pv, ev, ac = _pv_ev_ac(p.tareas, f)
        _, gr = gastos(db, p.id, f)
        real = f <= hoy
        serie.append(dict(fecha=f, pv=pv, ev=ev if real else None, ac=(ac + gr) if real else None))
    return serie


def costo_por_persona(p: Proyecto, hoy: date) -> list[dict]:
    prev, real = defaultdict(float), defaultdict(float)
    horas_p, horas_r = defaultdict(float), defaultdict(float)
    nombres = {}
    for t in p.tareas:
        k = t.persona_id
        nombres[k] = t.persona.nombre if t.persona else "Sin responsable"
        prev[k] += float(t.costo_previsto_base)
        horas_p[k] += t.horas_previstas
        for h in t.horas:
            if h.fecha <= hoy:
                real[h.persona_id] += h.horas * float(h.costo_hora_base)
                horas_r[h.persona_id] += h.horas
                nombres.setdefault(h.persona_id, f"Persona {h.persona_id}")
    return [dict(persona_id=k, nombre=nombres[k], costo_previsto=prev[k], costo_real=real[k],
                 horas_previstas=horas_p[k], horas_reales=horas_r[k]) for k in nombres]


def proyectos_activos(db: Session) -> list[Proyecto]:
    return db.scalars(select(Proyecto).where(Proyecto.estado.in_(
        [EstadoProyecto.en_curso, EstadoProyecto.pausado, EstadoProyecto.en_presupuesto])).order_by(Proyecto.fecha_inicio)).all()


def carga_equipo(db: Session, desde: date, semanas: int, horas_semana_empleado: float) -> list[dict]:
    """Horas reales y planificadas por persona y semana (lunes a domingo)."""
    from .models import Persona, TipoPersona
    lunes = desde - timedelta(days=desde.weekday())
    sem = [lunes + timedelta(weeks=i) for i in range(semanas)]
    personas = db.scalars(select(Persona).where(Persona.activo).order_by(Persona.nombre)).all()
    horas = db.scalars(select(HoraReal).where(HoraReal.fecha >= sem[0], HoraReal.fecha < sem[-1] + timedelta(days=7))).all()
    tareas = db.scalars(select(Tarea).where(Tarea.persona_id.is_not(None))).all()
    out = []
    for per in personas:
        filas = []
        for s in sem:
            fin_s = s + timedelta(days=6)
            reales = sum(h.horas for h in horas if h.persona_id == per.id and s <= h.fecha <= fin_s)
            plan = 0.0
            for t in tareas:
                if t.persona_id != per.id:
                    continue
                dias = (t.fecha_fin - t.fecha_inicio).days + 1
                solap = (min(t.fecha_fin, fin_s) - max(t.fecha_inicio, s)).days + 1
                if dias > 0 and solap > 0:
                    plan += t.horas_previstas * solap / dias
            filas.append(dict(semana=s, reales=reales, planificadas=plan))
        cap = horas_semana_empleado if per.tipo == TipoPersona.empleado else None
        out.append(dict(persona_id=per.id, nombre=per.nombre, tipo=per.tipo.value, capacidad_semanal=cap, semanas=filas))
    return out
