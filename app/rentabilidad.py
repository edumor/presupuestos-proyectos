# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Rentabilidad de un período: por proyecto, cliente, servicio, persona y flujo de caja mensual.

Criterios (todo en moneda base):
- Ingreso devengado: precio vigente del proyecto × avance ganado en el período (avance al cierre
  menos avance al inicio). Es lo que "se ganó" trabajando, se haya facturado o no.
- Costo: horas cargadas en el período × costo por hora congelado de cada registro (sueldo o tarifa
  más estructura) + gastos externos reales con fecha en el período.
- Facturado: neto de las facturas emitidas en el período (sin impuestos, a la cotización de cada una).
- Cobrado: cobros del período a la cotización del día; la diferencia de cambio es lo cobrado de más
  (o de menos) respecto de la cotización de la factura.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import contratos, costeo, facturacion, seguimiento
from .models import (Cobro, CostoExterno, Factura, HoraReal, Persona, PresupuestoItem, Proyecto, Servicio, Tarea,
                     TipoPersona)


def _ratio(a: float, b: float) -> float | None:
    return a / b if b else None


def _avance(db: Session, p: Proyecto, f: date) -> float:
    if p.fecha_inicio and f < p.fecha_inicio:
        return 0.0
    return seguimiento.metricas(db, p, f)["avance_ponderado"] if p.tareas else 0.0


def _meses(desde: date, hasta: date) -> list[date]:
    m, out = desde.replace(day=1), []
    while m <= hasta:
        out.append(m)
        m = contratos.sumar_meses(m, 1)
    return out


def calcular(db: Session, desde: date, hasta: date) -> dict:
    base = costeo.moneda_base(db)
    cfg = costeo.config(db)
    proyectos = db.scalars(select(Proyecto).order_by(Proyecto.nombre)).all()
    horas = db.scalars(select(HoraReal).where(HoraReal.fecha >= desde, HoraReal.fecha <= hasta)).all()
    gastos = db.scalars(select(CostoExterno).where(CostoExterno.es_real, CostoExterno.proyecto_id.is_not(None),
                                                   CostoExterno.fecha >= desde, CostoExterno.fecha <= hasta)).all()
    facturas = db.scalars(select(Factura).where(Factura.anulada.is_(False))).all()
    cobros = db.scalars(select(Cobro).join(Factura).where(Factura.anulada.is_(False), Cobro.fecha >= desde,
                                                          Cobro.fecha <= hasta)).all()
    tarea_proy = {t.id: t.proyecto_id for t in db.scalars(select(Tarea))}

    costo_h = defaultdict(float)
    for h in horas:
        costo_h[tarea_proy[h.tarea_id]] += h.horas * float(h.costo_hora_base)
    costo_g = defaultdict(float)
    for g in gastos:
        costo_g[g.proyecto_id] += float(g.importe_base)
    fact = defaultdict(float)
    for f in facturas:
        if desde <= f.fecha <= hasta:
            fact[f.proyecto_id] += float(f.neto_base)
    cob, dif = defaultdict(float), defaultdict(float)
    for c in cobros:
        cob[c.factura.proyecto_id] += float(c.importe_base)
        dif[c.factura.proyecto_id] += facturacion.diferencia_cambio(c)
    saldo = defaultdict(float)
    for f in facturas:
        if f.fecha <= hasta:
            saldo[f.proyecto_id] += facturacion.resumen(f, hasta)["saldo_base"]

    # --- por proyecto ---
    filas_p = []
    valor_hora = {}
    for p in proyectos:
        precio = contratos.precio_actual(db, p, hasta)["precio"] or 0.0
        horas_prev = sum(t.horas_previstas for t in p.tareas)
        valor_hora[p.id] = precio / horas_prev if horas_prev else 0.0
        av_ini = _avance(db, p, desde - timedelta(days=1)) if p.tareas else 0.0
        av_fin = _avance(db, p, hasta) if p.tareas else 0.0
        devengado = precio * max(av_fin - av_ini, 0.0)
        costo = costo_h[p.id] + costo_g[p.id]
        if not any([devengado, costo, fact[p.id], cob[p.id], saldo[p.id]]):
            continue
        margen = devengado - costo
        filas_p.append(dict(
            proyecto_id=p.id, proyecto=p.nombre, cliente_id=p.cliente_id,
            cliente=p.cliente.nombre if p.cliente else "", estado=p.estado.value, precio=precio,
            avance_inicio=av_ini, avance_fin=av_fin, devengado=round(devengado, 2),
            costo_horas=round(costo_h[p.id], 2), costo_gastos=round(costo_g[p.id], 2), costo=round(costo, 2),
            margen=round(margen, 2), margen_pct=_ratio(margen, devengado),
            facturado=round(fact[p.id], 2), cobrado=round(cob[p.id], 2), diferencia_cambio=round(dif[p.id], 2),
            saldo_a_cobrar=round(saldo[p.id], 2)))

    # --- por cliente ---
    cli: dict[int, dict] = {}
    for r in filas_p:
        c = cli.setdefault(r["cliente_id"], dict(cliente_id=r["cliente_id"], cliente=r["cliente"], proyectos=0,
                                                 devengado=0.0, costo=0.0, facturado=0.0, cobrado=0.0,
                                                 diferencia_cambio=0.0, saldo_a_cobrar=0.0))
        c["proyectos"] += 1
        for k in ("devengado", "costo", "facturado", "cobrado", "diferencia_cambio", "saldo_a_cobrar"):
            c[k] += r[k]
    filas_c = []
    for c in cli.values():
        c["margen"] = c["devengado"] - c["costo"]
        c["margen_pct"] = _ratio(c["margen"], c["devengado"])
        filas_c.append({k: round(v, 2) if isinstance(v, float) and k != "margen_pct" else v for k, v in c.items()})
    filas_c.sort(key=lambda c: -c["margen"])

    # --- por servicio: horas previstas para el avance logrado vs horas reales ---
    activos = {r["proyecto_id"] for r in filas_p}
    items = {i.id: i for i in db.scalars(select(PresupuestoItem))}
    servicios = {s.id: s.nombre for s in db.scalars(select(Servicio))}
    srv: dict[str, dict] = {}
    for p in proyectos:
        if p.id not in activos:
            continue
        for t in p.tareas:
            it = items.get(t.item_id)
            nombre = servicios.get(it.servicio_id) if it and it.servicio_id else None
            nombre = nombre or "Sin servicio del catálogo"
            av = seguimiento.avance_tarea(t, hasta)
            hr = sum(h.horas for h in t.horas if h.fecha <= hasta)
            cr = sum(h.horas * float(h.costo_hora_base) for h in t.horas if h.fecha <= hasta)
            s = srv.setdefault(nombre, dict(servicio=nombre, tareas=0, horas_previstas=0.0, horas_ganadas=0.0,
                                            horas_reales=0.0, costo_previsto=0.0, costo_ganado=0.0, costo_real=0.0))
            s["tareas"] += 1
            s["horas_previstas"] += t.horas_previstas
            s["horas_ganadas"] += t.horas_previstas * av
            s["horas_reales"] += hr
            s["costo_previsto"] += float(t.costo_previsto_base)
            s["costo_ganado"] += float(t.costo_previsto_base) * av
            s["costo_real"] += cr
    filas_s = []
    for s in srv.values():
        s["desvio_horas"] = _ratio(s["horas_reales"] - s["horas_ganadas"], s["horas_ganadas"])
        s["desvio_costo"] = _ratio(s["costo_real"] - s["costo_ganado"], s["costo_ganado"])
        filas_s.append({k: round(v, 2) if isinstance(v, float) and not k.startswith("desvio") else v
                        for k, v in s.items()})
    filas_s.sort(key=lambda s: -(s["desvio_horas"] or 0))

    # --- por persona ---
    dias = (hasta - desde).days + 1
    personas = {p.id: p for p in db.scalars(select(Persona))}
    per: dict[int, dict] = {}
    for h in horas:
        pid = tarea_proy[h.tarea_id]
        x = per.setdefault(h.persona_id, dict(horas=0.0, costo=0.0, valor=0.0, proyectos=set()))
        x["horas"] += h.horas
        x["costo"] += h.horas * float(h.costo_hora_base)
        x["valor"] += h.horas * valor_hora.get(pid, 0.0)
        x["proyectos"].add(pid)
    filas_per = []
    for pid, x in per.items():
        p = personas.get(pid)
        empleado = p is not None and p.tipo == TipoPersona.empleado
        anuales = cfg.horas_anuales if empleado else cfg.horas_autonomos_anuales
        disponibles = anuales * dias / 365 if empleado else None
        # los autónomos no tienen un objetivo de horas: se facturan las que se usan
        objetivo = anuales * cfg.utilizacion * dias / 365 if empleado else None
        filas_per.append(dict(
            persona_id=pid, persona=p.nombre if p else f"Persona {pid}", tipo=p.tipo.value if p else "",
            rol=p.rol.nombre if p and p.rol else "", proyectos=len(x["proyectos"]),
            horas=round(x["horas"], 2), horas_disponibles=round(disponibles, 1) if disponibles else None,
            horas_objetivo=round(objetivo, 1) if objetivo else None,
            utilizacion=_ratio(x["horas"], disponibles) if disponibles else None,
            cumplimiento_objetivo=_ratio(x["horas"], objetivo) if objetivo else None,
            costo=round(x["costo"], 2), valor=round(x["valor"], 2), margen=round(x["valor"] - x["costo"], 2),
            margen_pct=_ratio(x["valor"] - x["costo"], x["valor"])))
    filas_per.sort(key=lambda r: -r["horas"])

    # --- flujo de caja mensual ---
    meses = _meses(desde, hasta)
    flujo = {m: dict(mes=m, facturado=0.0, cobrado=0.0, costos=0.0, diferencia_cambio=0.0) for m in meses}
    for f in facturas:
        if desde <= f.fecha <= hasta:
            flujo[f.fecha.replace(day=1)]["facturado"] += facturacion.total(f) * float(f.cotizacion)
    for c in cobros:
        m = flujo[c.fecha.replace(day=1)]
        m["cobrado"] += float(c.importe_base)
        m["diferencia_cambio"] += facturacion.diferencia_cambio(c)
    for h in horas:
        flujo[h.fecha.replace(day=1)]["costos"] += h.horas * float(h.costo_hora_base)
    for g in gastos:
        flujo[g.fecha.replace(day=1)]["costos"] += float(g.importe_base)
    acum, filas_f = 0.0, []
    for m in meses:
        r = flujo[m]
        r["neto"] = r["cobrado"] - r["costos"]
        acum += r["neto"]
        r["acumulado"] = acum
        filas_f.append({k: round(v, 2) if isinstance(v, float) else v for k, v in r.items()})

    # cuentas a cobrar al cierre, por vencimiento
    pendientes = []
    for f in facturas:
        if f.fecha > hasta:
            continue
        r = facturacion.resumen(f, hasta)
        if r["saldo"] > 0:
            pendientes.append(dict(factura_id=f.id, numero=f.numero, proyecto=f.proyecto.nombre,
                                   cliente=f.proyecto.cliente.nombre if f.proyecto.cliente else "",
                                   fecha=f.fecha, vencimiento=f.vencimiento, moneda=f.moneda, saldo=r["saldo"],
                                   saldo_base=r["saldo_base"], estado=r["estado"], dias_vencida=r["dias_vencida"]))
    pendientes.sort(key=lambda x: (x["vencimiento"] or date.max))
    antig = {"Por vencer": 0.0, "1 a 30 días": 0.0, "31 a 60 días": 0.0, "Más de 60 días": 0.0}
    for x in pendientes:
        d = x["dias_vencida"] or 0
        k = "Por vencer" if not d else "1 a 30 días" if d <= 30 else "31 a 60 días" if d <= 60 else "Más de 60 días"
        antig[k] += x["saldo_base"]

    def tot(k):
        return round(sum(r[k] for r in filas_p), 2)
    dev, cos = tot("devengado"), tot("costo")
    return dict(
        desde=desde, hasta=hasta, moneda=base,
        totales=dict(devengado=dev, costo=cos, margen=round(dev - cos, 2), margen_pct=_ratio(dev - cos, dev),
                     facturado=tot("facturado"), cobrado=tot("cobrado"), diferencia_cambio=tot("diferencia_cambio"),
                     saldo_a_cobrar=round(sum(x["saldo_base"] for x in pendientes), 2),
                     vencido=round(sum(x["saldo_base"] for x in pendientes if x["estado"] == "vencida"), 2),
                     horas=round(sum(r["horas"] for r in filas_per), 2)),
        proyectos=filas_p, clientes=filas_c, servicios=filas_s, personas=filas_per,
        flujo=filas_f, a_cobrar=pendientes,
        antiguedad=[dict(tramo=k, saldo_base=round(v, 2)) for k, v in antig.items()],
    )
