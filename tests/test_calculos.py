# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Replica los ejemplos numéricos del documento de diseño."""
import pytest

from app.calculos import (LineaCosto, TareaEVM, calcular_presupuesto,
                          costo_directo_autonomo, costo_directo_empleado,
                          markup_equivalente, tasa_estructura, valor_ganado)

FX = 1.10        # USD por EUR
SS = 0.32
HORAS = 1760
UTIL = 0.70


def test_tasa_estructura():
    assert tasa_estructura(30000, 3964) == pytest.approx(7.57, abs=0.01)


def test_costo_hora_empleado():
    assert costo_directo_empleado(45000, SS, FX, HORAS, UTIL) == pytest.approx(53.04, abs=0.01)
    assert costo_directo_empleado(32000, SS, FX, HORAS, UTIL) == pytest.approx(37.71, abs=0.01)


def test_costo_hora_autonomo():
    assert costo_directo_autonomo(35, FX) == pytest.approx(38.50)


def test_presupuesto_ejemplo_documento():
    estr = tasa_estructura(30000, 3964)
    lineas = [
        LineaCosto("Project manager", 20, costo_directo_empleado(45000, SS, FX, HORAS, UTIL)),
        LineaCosto("SEO/SEM", 30, costo_directo_empleado(32000, SS, FX, HORAS, UTIL)),
        LineaCosto("Diseño", 40, costo_directo_autonomo(35, FX)),
        LineaCosto("Redes", 25, costo_directo_autonomo(30, FX)),
        LineaCosto("Desarrollo", 16, costo_directo_autonomo(100, FX)),
    ]
    r = calcular_presupuesto(lineas, estr, costos_externos=500, margen=0.35)
    assert r.horas_totales == 131
    assert r.costo_total == pytest.approx(7808.57, abs=0.05)
    assert r.precio == pytest.approx(12013.18, abs=0.05)
    assert r.ganancia == pytest.approx(4204.61, abs=0.05)
    assert r.markup == pytest.approx(0.538, abs=0.001)


def test_margen_invalido():
    with pytest.raises(ValueError):
        calcular_presupuesto([], 0, 100, margen=1.0)


def test_markup():
    assert markup_equivalente(0.35) == pytest.approx(0.5385, abs=0.0001)


def test_valor_ganado_ejemplo_documento():
    bac = 7808.57
    t = TareaEVM(costo_previsto=bac, pct_planificado=0.5, pct_real=0.4, costo_real=0.48 * bac)
    r = valor_ganado([t], precio=12013.18)
    assert r.cpi == pytest.approx(0.833, abs=0.001)
    assert r.spi == pytest.approx(0.80, abs=0.001)
    assert r.eac == pytest.approx(9370, abs=1)
    assert r.margen_proyectado == pytest.approx(0.22, abs=0.005)
