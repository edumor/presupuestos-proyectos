# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Motor de cálculo: costo por hora, precio y valor ganado.

Funciones puras, sin base de datos, para poder probarlas con tests.
Fórmulas según la sección "Modelo de costeo y fórmulas" del documento de diseño.
Las cotizaciones se expresan como unidades de la moneda base por 1 unidad de la moneda origen
(p. ej. con base ARS, 1 USD = 1.540 ARS -> base_por_unidad = 1540).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


# ---------- Costeo ----------

def horas_facturables_empleado(horas_anuales: float, utilizacion: float) -> float:
    return horas_anuales * utilizacion


def costo_directo_empleado(sueldo_bruto_anual: float, ss_empresa: float, base_por_unidad: float,
                           horas_anuales: float, utilizacion: float) -> float:
    """Costo por hora facturable de un empleado, en moneda base."""
    horas = horas_facturables_empleado(horas_anuales, utilizacion)
    if horas <= 0:
        raise ValueError("Las horas facturables deben ser mayores que cero")
    return sueldo_bruto_anual * (1 + ss_empresa) * base_por_unidad / horas


def costo_directo_autonomo(tarifa_hora: float, base_por_unidad: float) -> float:
    """Costo por hora de un autónomo, en moneda base."""
    return tarifa_hora * base_por_unidad


def tasa_estructura(costos_fijos_anuales_base: float, horas_facturables_anuales: float) -> float:
    """Costos fijos no facturables repartidos por hora facturable."""
    if horas_facturables_anuales <= 0:
        raise ValueError("Las horas facturables anuales deben ser mayores que cero")
    return costos_fijos_anuales_base / horas_facturables_anuales


def precio_desde_costo(costo: float, margen: float) -> float:
    """Margen sobre el precio: precio = costo / (1 - margen)."""
    if not 0 <= margen < 1:
        raise ValueError("El margen debe estar entre 0 y 1 (sin incluir 1)")
    return costo / (1 - margen)


def markup_equivalente(margen: float) -> float:
    return margen / (1 - margen)


@dataclass
class LineaCosto:
    descripcion: str
    horas: float
    costo_directo_hora: float


@dataclass
class ResultadoPresupuesto:
    costo_mano_obra: float
    costos_externos: float
    costo_total: float
    precio: float
    ganancia: float
    impuesto: float
    total_con_impuesto: float
    margen: float
    markup: float
    horas_totales: float


def calcular_presupuesto(lineas: list[LineaCosto], tasa_estructura_hora: float,
                         costos_externos: float, margen: float, impuesto: float = 0.0) -> ResultadoPresupuesto:
    mano_obra = sum(l.horas * (l.costo_directo_hora + tasa_estructura_hora) for l in lineas)
    costo = mano_obra + costos_externos
    precio = precio_desde_costo(costo, margen)
    imp = precio * impuesto
    return ResultadoPresupuesto(
        costo_mano_obra=mano_obra, costos_externos=costos_externos, costo_total=costo,
        precio=precio, ganancia=precio - costo, impuesto=imp, total_con_impuesto=precio + imp,
        margen=margen, markup=markup_equivalente(margen),
        horas_totales=sum(l.horas for l in lineas),
    )


# ---------- Valor ganado ----------

def avance_planificado(inicio: date, fin: date, a_fecha: date) -> float:
    """% que debería estar hecho a `a_fecha`, lineal entre inicio y fin."""
    if a_fecha <= inicio:
        return 0.0
    if a_fecha >= fin:
        return 1.0
    return (a_fecha - inicio).days / (fin - inicio).days


def avance_sugerido(horas_reales: float, horas_previstas: float) -> float:
    if horas_previstas <= 0:
        return 0.0
    return min(horas_reales / horas_previstas, 1.0)


@dataclass
class TareaEVM:
    costo_previsto: float      # BAC de la tarea
    pct_planificado: float     # 0..1 a la fecha
    pct_real: float            # 0..1
    costo_real: float          # AC de la tarea


@dataclass
class ResultadoEVM:
    bac: float
    pv: float
    ev: float
    ac: float
    cpi: float | None
    spi: float | None
    eac: float | None
    margen_proyectado: float | None


def valor_ganado(tareas: list[TareaEVM], precio: float, gastos_reales_extra: float = 0.0) -> ResultadoEVM:
    bac = sum(t.costo_previsto for t in tareas)
    pv = sum(t.costo_previsto * t.pct_planificado for t in tareas)
    ev = sum(t.costo_previsto * t.pct_real for t in tareas)
    ac = sum(t.costo_real for t in tareas) + gastos_reales_extra
    cpi = ev / ac if ac else None
    spi = ev / pv if pv else None
    eac = bac / cpi if cpi else None
    margen = (precio - eac) / precio if (eac is not None and precio) else None
    return ResultadoEVM(bac, pv, ev, ac, cpi, spi, eac, margen)
