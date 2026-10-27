# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Presupuestos: cálculo de cada versión, cambio de estado y aprobación.

Una versión en borrador o enviada se calcula con los costos vigentes (salvo ítems con costo por hora
manual). Al aprobarla se congelan el costo por hora de cada ítem, la tasa de estructura, el costo y el
precio, se fija el precio del proyecto y se generan sus tareas en las etapas correspondientes.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import calculos, costeo, seguimiento
from .models import (CostoExterno, Etapa, EstadoPresupuesto, EstadoProyecto, Persona, Presupuesto,
                     PresupuestoItem, Proyecto, Tarea)


class ErrorPresupuesto(Exception):
    pass


def costo_rol(db: Session, rol_id: int, a_fecha: date | None = None, tasa: float | None = None) -> float | None:
    """Costo total por hora promedio de las personas activas con ese rol."""
    ps = db.scalars(select(Persona).where(Persona.activo, Persona.rol_id == rol_id)).all()
    if not ps:
        return None
    return sum(costeo.costo_hora(db, p, a_fecha, tasa)["costo_total_base"] for p in ps) / len(ps)


def _horas_items(items: list[PresupuestoItem]) -> dict[int, float]:
    """Horas efectivas: las fijas, y las de los ítems "% sobre el total" calculadas sobre las fijas."""
    fijas = sum(i.horas or 0 for i in items if not i.pct_sobre_total)
    return {id(i): (fijas * i.pct_sobre_total if i.pct_sobre_total else (i.horas or 0)) for i in items}


def calcular(db: Session, pres: Presupuesto, a_fecha: date | None = None) -> dict:
    """Detalle con costos por ítem y resumen (costo, precio sugerido, precio final, margen real)."""
    congelado = pres.estado == EstadoPresupuesto.aprobado
    tasa = float(pres.tasa_estructura_base) if (congelado and pres.tasa_estructura_base is not None) \
        else costeo.estructura(db, a_fecha)["tasa_estructura_base"]
    horas = _horas_items(pres.items)
    filas, avisos = [], []
    for it in pres.items:
        origen = ("congelado" if congelado else "manual") if it.costo_hora_base is not None else None
        costo_h = float(it.costo_hora_base) if it.costo_hora_base is not None else None
        if costo_h is None and it.persona is not None:
            costo_h, origen = costeo.costo_hora(db, it.persona, a_fecha, tasa)["costo_total_base"], "persona"
        if costo_h is None and it.rol_id is not None:
            costo_h, origen = costo_rol(db, it.rol_id, a_fecha, tasa), "rol"
        if costo_h is None:
            avisos.append(f"«{it.tarea}» no tiene costo: elegí un rol con personas, un responsable o un costo por hora.")
        h = horas[id(it)]
        filas.append(dict(id=it.id, orden=it.orden, etapa=it.etapa, tarea=it.tarea, servicio_id=it.servicio_id,
                          servicio_nombre=it.servicio.nombre if it.servicio else None,
                          rol_id=it.rol_id, rol_nombre=it.rol.nombre if it.rol else None,
                          persona_id=it.persona_id, persona_nombre=it.persona.nombre if it.persona else None,
                          horas=h, horas_cargadas=it.horas, pct_sobre_total=it.pct_sobre_total,
                          costo_hora_manual=float(it.costo_hora_base) if (it.costo_hora_base is not None and not congelado) else None,
                          costo_hora=costo_h, origen_costo=origen,
                          costo=round(h * costo_h, 2) if costo_h is not None else None,
                          fecha_inicio=it.fecha_inicio, fecha_fin=it.fecha_fin))
    externos = [dict(id=g.id, concepto=g.concepto, moneda=g.moneda, importe=float(g.importe),
                     importe_base=_importe_base(db, g, congelado, a_fecha)) for g in pres.costos_externos]
    mano_obra = sum(f["costo"] or 0 for f in filas)
    ext = sum(e["importe_base"] for e in externos)
    costo = mano_obra + ext
    sugerido = calculos.precio_desde_costo(costo, pres.margen) if costo else 0.0
    precio = float(pres.precio_base) if pres.precio_base is not None else round(sugerido, 2)
    impuesto = round(precio * (pres.impuesto or 0), 2)
    return dict(
        id=pres.id, proyecto_id=pres.proyecto_id, version=pres.version, estado=pres.estado.value,
        margen=pres.margen, impuesto_pct=pres.impuesto or 0, notas=pres.notas,
        fecha_envio=pres.fecha_envio, fecha_aprobacion=pres.fecha_aprobacion,
        precio_manual=float(pres.precio_base) if (pres.precio_base is not None and not congelado) else None,
        items=filas, externos=externos, avisos=avisos,
        resumen=dict(horas=sum(f["horas"] for f in filas), tasa_estructura=tasa, costo_mano_obra=round(mano_obra, 2),
                     costos_externos=round(ext, 2), costo_total=round(costo, 2), precio_sugerido=round(sugerido, 2),
                     precio=precio, ganancia=round(precio - costo, 2),
                     margen_real=(precio - costo) / precio if precio else None,
                     markup=calculos.markup_equivalente(pres.margen), impuesto=impuesto,
                     total=round(precio + impuesto, 2)),
    )


def _importe_base(db: Session, g: CostoExterno, congelado: bool, a_fecha: date | None) -> float:
    if congelado and g.importe_base is not None:
        return float(g.importe_base)
    return round(costeo.a_base(db, float(g.importe), g.moneda, a_fecha), 2)


def nueva_version(db: Session, p: Proyecto, copiar_de: Presupuesto | None = None) -> Presupuesto:
    cfg = costeo.config(db)
    n = max((x.version for x in p.presupuestos), default=0) + 1
    base = copiar_de
    pres = Presupuesto(proyecto_id=p.id, version=n, estado=EstadoPresupuesto.borrador,
                       margen=base.margen if base else (p.margen if p.margen is not None else cfg.margen_defecto),
                       impuesto=base.impuesto if base else (p.impuesto or cfg.impuesto_defecto),
                       notas=base.notas if base else None)
    db.add(pres)
    if base:
        congelado = base.estado == EstadoPresupuesto.aprobado
        for it in base.items:  # los costos congelados no se copian: la nueva versión usa los vigentes
            pres.items.append(PresupuestoItem(
                servicio_id=it.servicio_id, tarea=it.tarea, etapa=it.etapa, pct_sobre_total=it.pct_sobre_total,
                rol_id=it.rol_id, persona_id=it.persona_id, horas=it.horas,
                costo_hora_base=None if congelado else it.costo_hora_base,
                fecha_inicio=it.fecha_inicio, fecha_fin=it.fecha_fin, orden=it.orden))
        for g in base.costos_externos:
            pres.costos_externos.append(CostoExterno(concepto=g.concepto, moneda=g.moneda, importe=g.importe,
                                                     cotizacion=1, importe_base=0, es_real=False))
    db.flush()
    return pres


def aprobar(db: Session, pres: Presupuesto, generar_tareas: bool = True, hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    if pres.estado == EstadoPresupuesto.aprobado:
        raise ErrorPresupuesto("Esta versión ya está aprobada.")
    p = pres.proyecto
    if any(x.estado == EstadoPresupuesto.aprobado for x in p.presupuestos if x.id != pres.id):
        raise ErrorPresupuesto("El proyecto ya tiene otra versión aprobada. Para cambiar el alcance, cargá las "
                               "diferencias como tareas en el proyecto.")
    d = calcular(db, pres, hoy)
    if d["avisos"]:
        raise ErrorPresupuesto(" ".join(d["avisos"]))
    if not d["items"]:
        raise ErrorPresupuesto("El presupuesto no tiene ítems.")
    # congelar
    for it, f in zip(pres.items, d["items"]):
        it.costo_hora_base = round(f["costo_hora"], 2)
        if not it.pct_sobre_total:
            it.horas = f["horas"]
    for g, e in zip(pres.costos_externos, d["externos"]):
        g.importe_base = e["importe_base"]
        g.cotizacion = costeo.base_por_unidad(db, g.moneda, hoy)
        g.fecha = hoy
    r = d["resumen"]
    pres.tasa_estructura_base = round(r["tasa_estructura"], 2)
    pres.costo_base, pres.precio_base = r["costo_total"], r["precio"]
    pres.estado, pres.fecha_aprobacion = EstadoPresupuesto.aprobado, hoy
    for x in p.presupuestos:  # las demás versiones abiertas quedan rechazadas
        if x.id != pres.id and x.estado in (EstadoPresupuesto.borrador, EstadoPresupuesto.enviado):
            x.estado = EstadoPresupuesto.rechazado
    # proyecto
    p.precio_base, p.margen, p.impuesto = r["precio"], pres.margen, pres.impuesto
    if p.estado == EstadoProyecto.en_presupuesto:
        p.estado = EstadoProyecto.en_curso
    for g in pres.costos_externos:  # los gastos previstos pasan al seguimiento del proyecto
        db.add(CostoExterno(proyecto_id=p.id, concepto=g.concepto, es_real=False, moneda=g.moneda,
                            importe=g.importe, cotizacion=g.cotizacion, importe_base=g.importe_base, fecha=hoy))
    if generar_tareas:
        _generar_tareas(db, p, pres, d)
    db.flush()


def _generar_tareas(db: Session, p: Proyecto, pres: Presupuesto, d: dict) -> None:
    if not p.etapas:
        p.etapas = seguimiento.etapas_desde_plantilla(db, p)
        db.flush()
    etapas = {e.nombre.strip().lower(): e for e in p.etapas}
    orden = max((t.orden for t in p.tareas), default=-1) + 1
    for it, f in zip(pres.items, d["items"]):
        e = etapas.get((it.etapa or "").strip().lower()) if it.etapa else None
        if it.etapa and e is None:
            e = Etapa(proyecto_id=p.id, nombre=it.etapa, orden=len(p.etapas))
            p.etapas.append(e)
            db.flush()
            etapas[it.etapa.strip().lower()] = e
        ini = it.fecha_inicio or (e.inicio_previsto if e else None) or p.fecha_inicio
        fin = it.fecha_fin or (e.fin_previsto if e else None) or p.fecha_fin
        if fin < ini:
            fin = ini
        if f["horas"] <= 0:
            continue
        db.add(Tarea(proyecto_id=p.id, etapa_id=e.id if e else None, item_id=it.id, nombre=it.tarea,
                     persona_id=it.persona_id, fecha_inicio=ini, fecha_fin=fin, horas_previstas=round(f["horas"], 2),
                     costo_hora_base=it.costo_hora_base,
                     costo_previsto_base=round(float(it.costo_hora_base) * f["horas"], 2), orden=orden))
        orden += 1
