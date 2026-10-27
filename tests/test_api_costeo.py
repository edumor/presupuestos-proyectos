# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date

import pytest


def test_ejemplo_reproduce_documento(client):
    assert client.post("/api/ejemplo").status_code == 200
    t = client.get("/api/tasa-estructura").json()
    # ARS: (USD 250 × 1.540 + 1.830.000) × 12 meses
    assert t["costos_fijos_anuales_base"] == pytest.approx(26_580_000)
    assert t["horas_facturables_anuales"] == pytest.approx(3964)
    tasa = 26_580_000 / 3964
    assert t["tasa_estructura_base"] == pytest.approx(tasa, abs=0.01)

    costos = {c["nombre"]: c for c in client.get("/api/costos-hora").json()}
    # empleados: 13 sueldos × (1 + 28,4 %) ÷ (1.760 h × 70 %) + estructura
    assert costos["Ana"]["costo_total_base"] == pytest.approx(13 * 2_600_000 * 1.284 / 1232 + tasa, abs=0.01)
    assert costos["Bruno"]["costo_total_base"] == pytest.approx(13 * 1_900_000 * 1.284 / 1232 + tasa, abs=0.01)
    assert costos["Carla"]["costo_total_base"] == pytest.approx(22_000 + tasa, abs=0.01)
    assert costos["Elena"]["costo_total_base"] == pytest.approx(45_000 + tasa, abs=0.01)


def test_borrar_ejemplo(client):
    client.post("/api/ejemplo")
    client.delete("/api/ejemplo")
    assert client.get("/api/personas").json() == []
    assert client.get("/api/costos-fijos").json() == []
    assert len(client.get("/api/roles").json()) == 8  # los roles quedan


def test_sin_cotizacion_da_422(client):
    rol = client.post("/api/roles", json={"nombre": "Diseño"}).json()
    p = client.post("/api/personas", json={"nombre": "X", "rol_id": rol["id"], "tipo": "autonomo",
                                            "moneda": "EUR", "tarifa_hora": 40}).json()
    r = client.get(f"/api/personas/{p['id']}/costo-hora")
    assert r.status_code == 422 and r.json()["moneda"] == "EUR"


def test_cotizacion_vigente_y_reemplazo(client):
    client.post("/api/cotizaciones", json={"fecha": "2026-10-01", "moneda": "eur", "valor": 1700})
    client.post("/api/cotizaciones", json={"fecha": "2026-10-20", "moneda": "EUR", "valor": 1750})
    client.post("/api/cotizaciones", json={"fecha": "2026-10-20", "moneda": "EUR", "valor": 1790})
    v = client.get("/api/cotizaciones/vigente", params={"moneda": "EUR", "fecha": "2026-10-15"}).json()
    assert v["valor"] == pytest.approx(1700)
    v = client.get("/api/cotizaciones/vigente", params={"moneda": "EUR", "fecha": str(date.today())}).json()
    assert v["valor"] == pytest.approx(1790)
    assert len(client.get("/api/cotizaciones", params={"moneda": "EUR"}).json()) == 2


def test_validaciones(client):
    rol = client.post("/api/roles", json={"nombre": "PM"}).json()
    # empleado sin sueldo
    r = client.post("/api/personas", json={"nombre": "X", "rol_id": rol["id"], "tipo": "empleado"})
    assert r.status_code == 422
    # rol duplicado
    assert client.post("/api/roles", json={"nombre": "PM"}).status_code == 409
    # moneda inválida y cotización de la propia moneda base
    r = client.post("/api/cotizaciones", json={"fecha": "2026-10-01", "moneda": "XYZ", "valor": 1000})
    assert r.status_code == 422
    r = client.post("/api/cotizaciones", json={"fecha": "2026-10-01", "moneda": "ARS", "valor": 1})
    assert r.status_code == 422
    # configuración fuera de rango
    cfg = client.get("/api/config").json()
    cfg["utilizacion"] = 1.5
    assert client.put("/api/config", json=cfg).status_code == 422


def test_moneda_base_configurable(client):
    cfg = client.get("/api/config").json()
    assert cfg["moneda_base"] == "ARS" and cfg["puede_cambiar_base"]
    cfg["moneda_base"] = "USD"
    assert client.put("/api/config", json=cfg).json()["moneda_base"] == "USD"
    # con base USD el ejemplo (en pesos) no se carga
    assert client.post("/api/ejemplo").status_code == 409
    cfg["moneda_base"] = "ARS"
    client.put("/api/config", json=cfg)
    client.post("/api/ejemplo")
    cfg = client.get("/api/config").json()
    assert not cfg["puede_cambiar_base"]
    cfg["moneda_base"] = "EUR"
    assert client.put("/api/config", json=cfg).status_code == 409


def test_datos_de_la_empresa(client):
    cfg = client.get("/api/config").json()
    cfg.update(empresa_nombre="Agencia X", empresa_direccion="Av. Siempreviva 742", empresa_localidad="Rosario",
               empresa_provincia="Santa Fe", empresa_cp="2000", empresa_pais="Argentina",
               empresa_telefonos="+54 341 555-0000", empresa_email="hola@agenciax.com.ar",
               empresa_web="agenciax.com.ar", empresa_id_fiscal="30-12345678-9")
    out = client.put("/api/config", json=cfg).json()
    assert out["empresa_localidad"] == "Rosario" and out["empresa_telefonos"] == "+54 341 555-0000"
    assert client.get("/api/config/logo").status_code == 404  # sin logo por defecto
