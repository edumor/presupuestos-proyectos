# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Datos para los documentos que se envían al cliente (propuesta e informe de avance).

Regla: nada de costos internos, márgenes, tarifas ni nombres del equipo.
El precio de cada etapa es el precio acordado repartido en proporción al costo previsto de
sus tareas (si no hay costos cargados, se reparte según el peso de cada etapa).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import CREDITO, costeo, i18n, seguimiento
from .config import logo_efectivo
from .models import Proyecto


def _repartir(total: float, pesos: list[float]) -> list[float]:
    """Reparte `total` según `pesos`, redondeado a centavos y sin diferencias de redondeo."""
    s = sum(pesos)
    if not pesos:
        return []
    if s <= 0:
        pesos, s = [1.0] * len(pesos), float(len(pesos))
    partes = [round(total * w / s, 2) for w in pesos]
    partes[-1] = round(total - sum(partes[:-1]), 2)
    return partes


def datos(db: Session, p: Proyecto, a_fecha: date | None = None, moneda: str | None = None,
          idioma: str = "es") -> dict:
    """`moneda`: otra moneda para mostrar también los importes (convertidos con la cotización vigente)."""
    hoy = a_fecha or date.today()
    cfg = costeo.config(db)
    tx = i18n.textos(idioma)
    idioma = idioma if idioma in i18n.IDIOMAS else "es"
    base = cfg.moneda_base
    m = seguimiento.metricas(db, p, hoy)

    tareas_por_etapa: dict[int | None, list] = {}
    for t in sorted(p.tareas, key=lambda t: (t.fecha_inicio, t.orden)):
        tareas_por_etapa.setdefault(t.etapa_id, []).append(t)

    filas = [e for e in m["etapas"]]
    precio = float(p.precio_base or 0)
    costos = [e["costo_previsto"] for e in filas]
    pesos = costos if sum(costos) > 0 else [e["peso_efectivo"] for e in filas]
    precios = _repartir(precio, pesos)

    etapas = []
    for e, pe in zip(filas, precios):
        ts = tareas_por_etapa.get(e["id"], [])
        etapas.append(dict(
            nombre=e["nombre"] if e["id"] is not None else tx["otras"],
            inicio=e["inicio_previsto"] or (min(t.fecha_inicio for t in ts) if ts else None),
            fin=e["fin_previsto"] or (max(t.fecha_fin for t in ts) if ts else None),
            inicio_real=e["inicio_real"], fin_real=e["fin_real"],
            hito=e["hito"], hito_cumplido=e["hito_cumplido"],
            aprobada=e["aprobada_cliente"], fecha_aprobacion=e["fecha_aprobacion"],
            horas=sum(t.horas_previstas for t in ts), precio=pe,
            avance=e["avance"], avance_planificado=e["avance_planificado"],
            estado=tx["estados"].get(e["estado"], e["estado"]), estado_cod=e["estado"],
            tareas=[dict(nombre=t.nombre, inicio=t.fecha_inicio, fin=t.fecha_fin,
                         avance=seguimiento.avance_tarea(t, hoy),
                         terminada=seguimiento.avance_tarea(t, hoy) >= 0.999 or t.fin_real is not None)
                    for t in ts],
        ))

    impuesto = round(precio * (p.impuesto or 0), 2)
    fx = None
    if moneda and moneda != base:
        cot = costeo.cotizacion_vigente(db, moneda, hoy)
        if cot is None:
            raise costeo.FaltaCotizacion(moneda)
        # valor = unidades de la base por 1 unidad de `moneda`; para convertir se divide
        fx = dict(moneda=moneda, valor=float(cot.valor), factor=1 / float(cot.valor), fecha=cot.fecha)

    logo = logo_efectivo()
    proximo = next((e for e in etapas if e["hito"] and not e["hito_cumplido"]), None)
    return dict(
        empresa=empresa(cfg, tx) | dict(logo=str(logo) if logo else None),
        credito=CREDITO, idioma=idioma, t=tx, moneda=base,
        proyecto=dict(id=p.id, nombre=p.nombre, cliente=p.cliente.nombre if p.cliente else "",
                      contacto=p.cliente.contacto if p.cliente else None, alcance=p.alcance or "",
                      inicio=p.fecha_inicio, fin=p.fecha_fin,
                      estado=tx["estados_proy"].get(p.estado.value, p.estado.value)),
        fecha=hoy, referencia=f"P{p.id:04d}-{hoy:%Y%m%d}",
        valido_hasta=hoy + timedelta(days=cfg.validez_dias or 30),
        condiciones=cfg.condiciones or "",
        etapas=etapas,
        horas_totales=sum(e["horas"] for e in etapas),
        precio=precio, impuesto_pct=p.impuesto or 0, impuesto=impuesto, total=round(precio + impuesto, 2),
        fx=fx,
        avance=m["avance_ponderado"], avance_planificado=m["avance_planificado"],
        etapas_terminadas=sum(1 for e in etapas if e["estado_cod"] == "terminada"),
        etapas_aprobadas=sum(1 for e in etapas if e["aprobada"]),
        proximo_hito=dict(etapa=proximo["nombre"], hito=proximo["hito"], fecha=proximo["fin"]) if proximo else None,
    )


def empresa(cfg, t: dict) -> dict:
    """Datos de la empresa para el encabezado: nombre y líneas de contacto ya armadas."""
    localidad = ", ".join(x for x in [
        " ".join(x for x in [cfg.empresa_cp, cfg.empresa_localidad] if x), cfg.empresa_provincia,
        cfg.empresa_pais] if x)
    lineas = [cfg.empresa_direccion, localidad,
              f"{t['tel']} {cfg.empresa_telefonos}" if cfg.empresa_telefonos else None,
              " · ".join(x for x in [cfg.empresa_email, cfg.empresa_web] if x),
              f"{t['id_fiscal']}: {cfg.empresa_id_fiscal}" if cfg.empresa_id_fiscal else None]
    return dict(nombre=cfg.empresa_nombre or "", lineas=[x for x in lineas if x],
                email=cfg.empresa_email or "", web=cfg.empresa_web or "")


def convertir(d: dict, importe_base: float) -> float | None:
    return round(importe_base * d["fx"]["factor"], 2) if d.get("fx") else None


def _fx(db: Session, moneda: str | None, base: str, hoy: date) -> dict | None:
    if not moneda or moneda == base:
        return None
    cot = costeo.cotizacion_vigente(db, moneda, hoy)
    if cot is None:
        raise costeo.FaltaCotizacion(moneda)
    return dict(moneda=moneda, valor=float(cot.valor), factor=1 / float(cot.valor), fecha=cot.fecha)


def datos_presupuesto(db: Session, pres, a_fecha: date | None = None, moneda: str | None = None,
                      idioma: str = "es") -> dict:
    """Propuesta armada desde una versión de presupuesto (antes de que existan las tareas del proyecto).

    Las etapas siguen el orden de las del proyecto; cada ítem es una actividad. El precio de cada etapa
    es el precio de la versión repartido según el costo de sus ítems.
    """
    from . import presupuestos
    hoy = a_fecha or date.today()
    cfg = costeo.config(db)
    tx = i18n.textos(idioma)
    idioma = idioma if idioma in i18n.IDIOMAS else "es"
    p = pres.proyecto
    calc = presupuestos.calcular(db, pres, hoy)
    etapas_p = {e.nombre.strip().lower(): e for e in p.etapas}
    orden = {e.nombre.strip().lower(): e.orden for e in p.etapas}
    grupos: dict[str, list] = {}
    for f in calc["items"]:
        clave = (f["etapa"] or "").strip()
        grupos.setdefault(clave, []).append(f)
    claves = sorted(grupos, key=lambda k: (k == "", orden.get(k.lower(), 999)))
    costos = [sum(f["costo"] or 0 for f in grupos[k]) for k in claves]
    precio = calc["resumen"]["precio"]
    precios = _repartir(precio, costos if sum(costos) > 0 else [1.0] * len(claves))
    etapas = []
    for k, pe in zip(claves, precios):
        e = etapas_p.get(k.lower())
        fs = grupos[k]
        ini = e.inicio_previsto if e and e.inicio_previsto else min((f["fecha_inicio"] for f in fs if f["fecha_inicio"]),
                                                                    default=p.fecha_inicio)
        fin = e.fin_previsto if e and e.fin_previsto else max((f["fecha_fin"] for f in fs if f["fecha_fin"]),
                                                              default=p.fecha_fin)
        etapas.append(dict(nombre=k or tx["otras"], inicio=ini, fin=fin, hito=e.hito if e else None,
                           hito_cumplido=None, aprobada=False, fecha_aprobacion=None,
                           horas=sum(f["horas"] for f in fs), precio=pe, avance=0, avance_planificado=0,
                           estado=tx["estados"]["no iniciada"], estado_cod="no iniciada",
                           tareas=[dict(nombre=f["tarea"], inicio=f["fecha_inicio"] or ini, fin=f["fecha_fin"] or fin,
                                        avance=0, terminada=False) for f in fs]))
    impuesto = calc["resumen"]["impuesto"]
    logo = logo_efectivo()
    return dict(
        empresa=empresa(cfg, tx) | dict(logo=str(logo) if logo else None),
        credito=CREDITO, idioma=idioma, t=tx, moneda=cfg.moneda_base,
        proyecto=dict(id=p.id, nombre=p.nombre, cliente=p.cliente.nombre if p.cliente else "",
                      contacto=p.cliente.contacto if p.cliente else None, alcance=p.alcance or "",
                      inicio=p.fecha_inicio, fin=p.fecha_fin,
                      estado=tx["estados_proy"].get(p.estado.value, p.estado.value)),
        fecha=hoy, referencia=f"P{p.id:04d}-V{pres.version}-{hoy:%Y%m%d}",
        valido_hasta=hoy + timedelta(days=cfg.validez_dias or 30),
        condiciones=cfg.condiciones or "", etapas=etapas,
        horas_totales=sum(e["horas"] for e in etapas),
        precio=precio, impuesto_pct=pres.impuesto or 0, impuesto=impuesto, total=round(precio + impuesto, 2),
        fx=_fx(db, moneda, cfg.moneda_base, hoy),
    )
