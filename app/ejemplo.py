# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Datos de ejemplo (marcados es_ejemplo): una agencia argentina de marketing digital en pesos.

Valores de referencia de octubre de 2026, para conocer el sistema (no son una recomendación):
- Empleados en relación de dependencia: sueldo bruto anual = 13 sueldos (incluye aguinaldo).
  Contribuciones patronales 28,4 % = 20,4 % seguridad social + 6 % obra social + ~2 % ART.
- Autónomos (monotributistas) que facturan por hora en pesos.
- Costos fijos en pesos y una licencia de software en dólares (se convierte con la cotización).
- Cotizaciones: 1 USD = 1.540 ARS (BNA, venta), EUR, GBP y BRL aproximadas.
"""
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import costeo, seguimiento
from .models import (Cliente, CostoExterno, CostoFijo, Cotizacion, EstadoProyecto, HoraReal,
                     Periodicidad, Persona, Proyecto, Rol, Servicio, Tarea, TipoPersona)

MONEDA = "ARS"

ROLES = ["Project manager", "Especialista SEO/SEM", "Diseñador gráfico",
         "Especialista redes sociales", "Desarrollador web", "Redactor",
         "Especialista email", "Analista"]

PERSONAS = [  # nombre, rol, tipo, sueldo bruto anual ARS (13 sueldos), tarifa ARS/h
    ("Ana", "Project manager", TipoPersona.empleado, 13 * 2_600_000, None),
    ("Bruno", "Especialista SEO/SEM", TipoPersona.empleado, 13 * 1_900_000, None),
    ("Carla", "Diseñador gráfico", TipoPersona.autonomo, None, 22_000),
    ("Diego", "Especialista redes sociales", TipoPersona.autonomo, None, 18_000),
    ("Elena", "Desarrollador web", TipoPersona.autonomo, None, 45_000),
    ("Fede", "Redactor", TipoPersona.autonomo, None, 16_000),
    ("Gina", "Analista", TipoPersona.autonomo, None, 28_000),
    ("Hugo", "Especialista email", TipoPersona.autonomo, None, 17_000),
]

COSTOS_FIJOS = [  # concepto, moneda, importe por mes
    ("Software y licencias", "USD", 250),
    ("Oficina / coworking", "ARS", 900_000),
    ("Servicios (internet, luz, telefonía)", "ARS", 180_000),
    ("Estudio contable", "ARS", 350_000),
    ("Horas de administración no facturables", "ARS", 400_000),
]

# Cotizaciones: unidades de ARS por 1 unidad de la moneda (hoy y hace 120 días)
COTIZACIONES = {"USD": (1540, 1435), "EUR": (1790, 1650), "GBP": (2065, 1915), "BRL": (285, 262)}

SERVICIOS = [  # nombre, rol sugerido, horas, % sobre total, etapa sugerida
    ("Reunión de kick-off y brief", "Project manager", 6, None, "Inicio"),
    ("Estrategia y planificación de campaña", "Project manager", 12, None, "Planificación"),
    ("Auditoría SEO", "Especialista SEO/SEM", 16, None, "Planificación"),
    ("Gestión de campañas de pago (setup)", "Especialista SEO/SEM", 10, None, "Ejecución"),
    ("Gestión de redes sociales (mes)", "Especialista redes sociales", 25, None, "Ejecución"),
    ("Diseño de piezas gráficas (paquete de 10)", "Diseñador gráfico", 20, None, "Ejecución"),
    ("Landing page", "Desarrollador web", 16, None, "Ejecución"),
    ("Sitio web institucional (hasta 6 secciones)", "Desarrollador web", 60, None, "Ejecución"),
    ("Redacción de contenidos (4 artículos)", "Redactor", 16, None, "Ejecución"),
    ("Email marketing (campaña)", "Especialista email", 8, None, "Ejecución"),
    ("Reportes y analítica (mes)", "Analista", 6, None, "Cierre"),
    ("Reuniones y gestión del proyecto", "Project manager", None, 0.10, "Ejecución"),
]


class BaseNoCompatible(Exception):
    pass


def hay_ejemplo(db: Session) -> bool:
    return db.scalars(select(Persona).where(Persona.es_ejemplo)).first() is not None


def cargar(db: Session) -> None:
    if hay_ejemplo(db):
        return
    cfg = costeo.config(db)
    if cfg.moneda_base != MONEDA:
        raise BaseNoCompatible(f"Los datos de ejemplo están en pesos (ARS) y la moneda base es {cfg.moneda_base}.")
    cfg.horas_anuales, cfg.utilizacion, cfg.ss_empresa_defecto = 1760, 0.70, 0.284
    cfg.margen_defecto, cfg.margen_alerta, cfg.horas_autonomos_anuales = 0.35, 0.25, 1500

    roles = {r.nombre: r for r in db.scalars(select(Rol))}
    for n in ROLES:
        if n not in roles:
            roles[n] = Rol(nombre=n)
            db.add(roles[n])
    db.flush()

    hoy = date.today()
    inicio_hist = hoy - timedelta(days=120)  # para poder costear las horas pasadas del ejemplo
    for moneda, (actual, anterior) in COTIZACIONES.items():
        if costeo.cotizacion_vigente(db, moneda, inicio_hist) is None:
            db.add(Cotizacion(fecha=inicio_hist, moneda=moneda, valor=anterior))
        if costeo.cotizacion_vigente(db, moneda) is None or costeo.cotizacion_vigente(db, moneda).fecha != hoy:
            db.add(Cotizacion(fecha=hoy, moneda=moneda, valor=actual))
    db.flush()

    for nombre, rol, tipo, sueldo, tarifa in PERSONAS:
        db.add(Persona(nombre=nombre, rol_id=roles[rol].id, tipo=tipo, moneda=MONEDA,
                       sueldo_bruto_anual=sueldo, tarifa_hora=tarifa, es_ejemplo=True))
    for concepto, moneda, mensual in COSTOS_FIJOS:
        db.add(CostoFijo(concepto=concepto, moneda=moneda, importe=mensual,
                         periodicidad=Periodicidad.mensual, es_ejemplo=True))
    for nombre, rol, horas, pct, etapa in SERVICIOS:
        db.add(Servicio(nombre=nombre, rol_sugerido_id=roles[rol].id, horas_sugeridas=horas,
                        pct_sobre_total=pct, etapa_sugerida=etapa, es_ejemplo=True))
    cliente = Cliente(nombre="Cliente de ejemplo S.A.", pais="Argentina", moneda_mostrar="USD", es_ejemplo=True)
    db.add(cliente)
    db.commit()
    seguimiento.asegurar_plantilla(db)
    _proyectos_ejemplo(db, cliente)
    _presupuesto_ejemplo(db, cliente)


def _presupuesto_ejemplo(db: Session, cliente: Cliente) -> None:
    """Un proyecto "en presupuesto" con una versión enviada armada desde el catálogo."""
    from .models import EstadoPresupuesto, PresupuestoItem
    from . import presupuestos
    hoy = date.today()
    p = Proyecto(cliente_id=cliente.id, nombre="Rediseño del sitio web", fecha_inicio=hoy + timedelta(days=14),
                 fecha_fin=hoy + timedelta(days=14 + 69), estado=EstadoProyecto.en_presupuesto, margen=0.35,
                 es_ejemplo=True, alcance="Rediseño del sitio institucional, landing de campaña y contenidos iniciales.")
    db.add(p)
    p.etapas = seguimiento.etapas_desde_plantilla(db, p)
    db.flush()
    pres = presupuestos.nueva_version(db, p)
    servicios = {s.nombre: s for s in db.scalars(select(Servicio).where(Servicio.es_ejemplo))}
    for i, n in enumerate(["Reunión de kick-off y brief", "Estrategia y planificación de campaña",
                           "Sitio web institucional (hasta 6 secciones)", "Landing page",
                           "Diseño de piezas gráficas (paquete de 10)", "Redacción de contenidos (4 artículos)",
                           "Reuniones y gestión del proyecto", "Reportes y analítica (mes)"]):
        s = servicios[n]
        pres.items.append(PresupuestoItem(servicio_id=s.id, tarea=s.nombre, etapa=s.etapa_sugerida,
                                          rol_id=s.rol_sugerido_id, horas=s.horas_sugeridas or 0,
                                          pct_sobre_total=s.pct_sobre_total, orden=i))
    pres.costos_externos.append(CostoExterno(concepto="Hosting y dominio (1 año)", moneda="USD", importe=180,
                                             cotizacion=1, importe_base=0, es_real=False))
    pres.estado, pres.fecha_envio = EstadoPresupuesto.enviado, hoy - timedelta(days=2)
    db.commit()


# Tareas de ejemplo: etapa, nombre, persona, horas, inicio (días desde el arranque), duración (días),
# factor de horas reales (>1 = consumió más de lo previsto), factor de avance (<1 = va más lento)
TAREAS_CAMPANA = [
    ("Inicio", "Kick-off y brief", "Ana", 6, 0, 7, 1.0, 1.0),
    ("Planificación", "Estrategia y calendario", "Ana", 12, 7, 14, 1.1, 1.0),
    ("Planificación", "Auditoría SEO inicial", "Bruno", 16, 7, 14, 1.2, 0.95),
    ("Ejecución", "Diseño de piezas gráficas", "Carla", 40, 21, 35, 1.25, 0.8),
    ("Ejecución", "Landing page", "Elena", 16, 28, 21, 1.1, 0.85),
    ("Ejecución", "Campañas de pago", "Bruno", 14, 35, 35, 1.0, 0.9),
    ("Ejecución", "Gestión de redes sociales", "Diego", 25, 21, 49, 1.05, 0.9),
    ("Cierre", "Reporte final y presentación", "Gina", 6, 70, 14, 1.0, 1.0),
    ("Cierre", "Gestión y reuniones de cierre", "Ana", 4, 74, 10, 1.0, 1.0),
]
TAREAS_AUDITORIA = [
    ("Inicio", "Relevamiento", "Bruno", 4, 0, 4, 0.9, 1.0),
    ("Planificación", "Plan de auditoría", "Bruno", 4, 4, 5, 0.9, 1.05),
    ("Ejecución", "Auditoría técnica y de contenidos", "Bruno", 18, 9, 22, 0.95, 1.1),
    ("Cierre", "Informe y recomendaciones", "Gina", 6, 31, 9, 1.0, 1.0),
]


def _proyectos_ejemplo(db: Session, cliente: Cliente) -> None:
    hoy = date.today()
    personas = {p.nombre: p for p in db.scalars(select(Persona).where(Persona.es_ejemplo))}
    definiciones = [
        # gastos externos en USD: concepto, previsto, real
        ("Campaña de lanzamiento", hoy - timedelta(days=42), 84, TAREAS_CAMPANA,
         [("Bancos de imágenes", 300, 380), ("Licencia de herramienta SEO", 200, 200)]),
        ("Auditoría SEO", hoy - timedelta(days=30), 40, TAREAS_AUDITORIA, []),
    ]
    for nombre, inicio, dias, tareas, gastos in definiciones:
        p = Proyecto(cliente_id=cliente.id, nombre=nombre, fecha_inicio=inicio,
                     fecha_fin=inicio + timedelta(days=dias - 1), estado=EstadoProyecto.en_curso,
                     margen=0.35, es_ejemplo=True,
                     alcance="Proyecto ficticio para conocer el sistema.")
        db.add(p)
        p.etapas = seguimiento.etapas_desde_plantilla(db, p)
        db.flush()
        etapas = {e.nombre: e for e in p.etapas}
        costo_tareas = 0.0
        for i, (etapa, tnombre, quien, horas, ini, dur, f_horas, f_avance) in enumerate(tareas):
            per = personas[quien]
            costo = round(costeo.costo_hora(db, per, inicio)["costo_total_base"], 2)
            t = Tarea(proyecto_id=p.id, etapa_id=etapas[etapa].id, nombre=tnombre, persona_id=per.id,
                      fecha_inicio=inicio + timedelta(days=ini), fecha_fin=inicio + timedelta(days=ini + dur - 1),
                      horas_previstas=horas, costo_hora_base=costo, costo_previsto_base=round(costo * horas, 2), orden=i)
            db.add(t)
            costo_tareas += float(t.costo_previsto_base)
            _simular_avance(db, t, per, f_horas, f_avance, hoy)
        # etapas ya cumplidas
        for e in p.etapas:
            if e.fin_previsto and e.fin_previsto < hoy - timedelta(days=3):
                e.inicio_real, e.fin_real = e.inicio_previsto, e.fin_previsto + timedelta(days=2)
                e.hito_cumplido = e.fin_real
                e.aprobada_cliente, e.fecha_aprobacion = True, e.fin_real + timedelta(days=1)
            elif e.inicio_previsto and e.inicio_previsto <= hoy:
                e.inicio_real = e.inicio_previsto
        externos = 0.0
        for concepto, previsto, real in gastos:
            for es_real, importe, fecha in ((False, previsto, inicio), (True, real, inicio + timedelta(days=25))):
                fx = costeo.base_por_unidad(db, "USD", fecha)
                db.add(CostoExterno(proyecto_id=p.id, concepto=concepto, es_real=es_real, moneda="USD",
                                    importe=importe, cotizacion=fx, importe_base=round(importe * fx, 2), fecha=fecha))
                if not es_real:
                    externos += importe * fx
        # precio acordado: costo previsto con 35 % de margen, redondeado a $10.000
        p.precio_base = round((costo_tareas + externos) / (1 - p.margen), -4)
    db.commit()


def _simular_avance(db: Session, t: Tarea, per: Persona, f_horas: float, f_avance: float, hoy: date) -> None:
    """Horas por día hábil y avance semanal, determinísticos, hasta ayer."""
    dias = [t.fecha_inicio + timedelta(days=d) for d in range((t.fecha_fin - t.fecha_inicio).days + 1)]
    habiles = [d for d in dias if d.weekday() < 5] or dias
    por_dia = t.horas_previstas * f_horas / len(habiles)
    costo = round(costeo.costo_hora(db, per, t.fecha_inicio)["costo_total_base"], 2)
    for d in habiles:
        if d >= hoy:
            break
        t.horas.append(HoraReal(persona_id=per.id, fecha=d, horas=round(por_dia, 2), costo_hora_base=costo))
    d = t.fecha_inicio + timedelta(days=6)
    while d < hoy:
        plan = min((d - t.fecha_inicio).days + 1, len(dias)) / len(dias)
        seguimiento.registrar_avance(db, t, round(min(plan * f_avance, 1.0), 2), d)
        if d >= t.fecha_fin:
            break
        d += timedelta(days=7)
    if t.fecha_fin < hoy:
        seguimiento.registrar_avance(db, t, 1.0, min(t.fecha_fin + timedelta(days=2), hoy - timedelta(days=1)))
        t.inicio_real, t.fin_real = t.fecha_inicio, t.fecha_fin + timedelta(days=2)
    elif t.fecha_inicio < hoy:
        t.inicio_real = t.fecha_inicio


def borrar(db: Session) -> None:
    """Borra solo lo marcado como ejemplo; roles y cotizaciones quedan."""
    for p in db.scalars(select(Proyecto).where(Proyecto.es_ejemplo)).all():
        db.execute(delete(CostoExterno).where(CostoExterno.proyecto_id == p.id))
        db.delete(p)
    db.flush()
    for modelo in (Servicio, Persona, CostoFijo, Cliente):
        db.execute(delete(modelo).where(modelo.es_ejemplo))
    db.commit()
