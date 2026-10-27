# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Facturas, cobros, diferencia de cambio y tableros de rentabilidad."""
import io
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook


@pytest.fixture()
def base(client):
    client.post("/api/cotizaciones", json={"fecha": "2026-01-01", "moneda": "USD", "valor": 1000})
    client.post("/api/cotizaciones", json={"fecha": "2026-03-01", "moneda": "USD", "valor": 1100})
    rol = client.post("/api/roles", json={"nombre": "Diseño"}).json()
    per = client.post("/api/personas", json={"nombre": "Ana", "rol_id": rol["id"], "tipo": "autonomo",
                                              "moneda": "ARS", "tarifa_hora": 50}).json()
    cfg = client.get("/api/config").json()
    client.put("/api/config", json={**cfg, "horas_autonomos_anuales": 0})  # costo/hora = 50 exacto
    cli = client.post("/api/clientes", json={"nombre": "Cliente A"}).json()
    p = client.post("/api/proyectos", json={"cliente_id": cli["id"], "nombre": "Web", "fecha_inicio": "2026-01-05",
                                            "fecha_fin": "2026-02-27", "precio_base": 2000,
                                            "usar_plantilla": False}).json()
    return client, per, cli, p


def test_factura_y_cobros_en_moneda_base(base):
    client, _, _, p = base
    f = client.post(f"/api/proyectos/{p['id']}/facturas", json={
        "numero": "A-0001-00000012", "fecha": "2026-01-10", "vencimiento": "2026-01-25",
        "importe_neto": 1000, "impuesto": 210}).json()
    assert f["moneda"] == "ARS" and f["total"] == 1210 and f["neto_base"] == 1000 and f["estado"] == "vencida"
    f = client.post(f"/api/facturas/{f['id']}/cobros", json={"fecha": "2026-01-20", "importe": 600}).json()
    assert f["cobrado"] == 600 and f["saldo"] == 610
    r = client.post(f"/api/facturas/{f['id']}/cobros", json={"fecha": "2026-01-21", "importe": 700})
    assert r.status_code == 422 and "saldo" in r.json()["detail"]
    f = client.post(f"/api/facturas/{f['id']}/cobros", json={"fecha": "2026-01-22", "importe": 610}).json()
    assert f["estado"] == "cobrada" and f["saldo"] == 0
    res = client.get(f"/api/proyectos/{p['id']}/facturas").json()
    assert res["facturado"] == 1000 and res["por_facturar"] == 1000 and res["pct_facturado"] == pytest.approx(0.5)
    # no se puede bajar el total por debajo de lo cobrado
    r = client.put(f"/api/facturas/{f['id']}", json={"fecha": "2026-01-10", "importe_neto": 500})
    assert r.status_code == 422


def test_factura_en_dolares_con_diferencia_de_cambio(base):
    client, _, _, p = base
    client.put(f"/api/proyectos/{p['id']}", json={**p, "moneda_contrato": "USD", "precio_contrato": 2})
    f = client.post(f"/api/proyectos/{p['id']}/facturas", json={"fecha": "2026-02-01", "importe_neto": 1}).json()
    assert f["moneda"] == "USD" and f["cotizacion"] == 1000 and f["neto_base"] == 1000
    f = client.post(f"/api/facturas/{f['id']}/cobros", json={"fecha": "2026-03-05", "importe": 1}).json()
    c = f["cobros"][0]
    assert c["cotizacion"] == 1100 and c["importe_base"] == 1100 and c["diferencia_cambio"] == 100
    assert f["diferencia_cambio"] == 100
    res = client.get(f"/api/proyectos/{p['id']}/facturas").json()
    assert res["moneda"] == "USD" and res["facturado"] == 1 and res["por_facturar"] == 1
    # cotización manual
    f2 = client.post(f"/api/proyectos/{p['id']}/facturas", json={"fecha": "2026-02-01", "importe_neto": 1,
                                                                 "cotizacion": 1050}).json()
    assert f2["neto_base"] == 1050
    # la anulada no suma
    client.put(f"/api/facturas/{f2['id']}", json={"fecha": "2026-02-01", "importe_neto": 1, "anulada": True})
    assert client.get(f"/api/proyectos/{p['id']}/facturas").json()["facturado"] == 1


def test_rentabilidad_del_periodo(base):
    client, per, cli, p = base
    t = client.post(f"/api/proyectos/{p['id']}/tareas", json={
        "nombre": "Diseño", "persona_id": per["id"], "fecha_inicio": "2026-01-05", "fecha_fin": "2026-02-27",
        "horas_previstas": 20}).json()
    client.post("/api/horas", json={"tarea_id": t["id"], "persona_id": per["id"], "fecha": "2026-01-15", "horas": 10})
    client.post("/api/horas", json={"tarea_id": t["id"], "persona_id": per["id"], "fecha": "2026-02-10", "horas": 6})
    client.post(f"/api/proyectos/{p['id']}/gastos", json={"concepto": "Hosting", "es_real": True, "importe": 100,
                                                         "fecha": "2026-02-01"})
    f = client.post(f"/api/proyectos/{p['id']}/facturas", json={"fecha": "2026-01-31", "vencimiento": "2026-02-15",
                                                                "importe_neto": 1000}).json()
    client.post(f"/api/facturas/{f['id']}/cobros", json={"fecha": "2026-02-10", "importe": 400})

    r = client.get("/api/rentabilidad", params={"desde": "2026-01-01", "hasta": "2026-01-31"}).json()
    x = r["proyectos"][0]
    assert x["avance_fin"] == pytest.approx(0.5)            # 10 de 20 horas
    assert x["devengado"] == pytest.approx(1000)            # 2000 × 50 %
    assert x["costo"] == pytest.approx(500) and x["margen"] == pytest.approx(500)
    assert x["facturado"] == 1000 and x["cobrado"] == 0

    r = client.get("/api/rentabilidad", params={"desde": "2026-02-01", "hasta": "2026-02-28"}).json()
    x = r["proyectos"][0]
    assert x["avance_inicio"] == pytest.approx(0.5) and x["avance_fin"] == pytest.approx(0.8)
    assert x["devengado"] == pytest.approx(600) and x["costo"] == pytest.approx(400)  # 300 horas + 100 gasto
    assert x["cobrado"] == 400 and x["saldo_a_cobrar"] == 600
    assert r["totales"]["vencido"] == 600 and r["a_cobrar"][0]["dias_vencida"] == 13
    assert r["clientes"][0]["cliente"] == "Cliente A" and r["clientes"][0]["margen"] == pytest.approx(200)
    s = r["servicios"][0]
    assert s["servicio"] == "Sin servicio del catálogo" and s["horas_reales"] == 16 and s["horas_ganadas"] == 16
    pe = r["personas"][0]
    assert pe["horas"] == 6 and pe["costo"] == 300 and pe["valor"] == pytest.approx(600)  # 2000/20 por hora
    fl = r["flujo"]
    assert len(fl) == 1 and fl[0]["cobrado"] == 400 and fl[0]["costos"] == 400 and fl[0]["neto"] == 0

    # el año completo: tres meses en el flujo, acumulado coherente
    r = client.get("/api/rentabilidad", params={"desde": "2026-01-01", "hasta": "2026-03-31"}).json()
    assert [m["mes"] for m in r["flujo"]] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert r["flujo"][-1]["acumulado"] == pytest.approx(400 - 500 - 400)
    assert client.get("/api/rentabilidad", params={"desde": "2026-03-01", "hasta": "2026-01-01"}).status_code == 422

    xl = client.get("/api/export/rentabilidad", params={"desde": "2026-01-01", "hasta": "2026-03-31"})
    assert xl.status_code == 200
    wb = load_workbook(io.BytesIO(xl.content))
    assert wb.sheetnames == ["Resumen", "Proyectos", "Clientes", "Servicios", "Personas", "Flujo de caja", "A cobrar"]


def test_borrar_proyecto_con_facturas(base):
    client, _, _, p = base
    f = client.post(f"/api/proyectos/{p['id']}/facturas", json={"fecha": "2026-01-10", "importe_neto": 10}).json()
    client.post(f"/api/facturas/{f['id']}/cobros", json={"fecha": str(date(2026, 1, 10) + timedelta(days=1)),
                                                        "importe": 5})
    assert client.delete(f"/api/proyectos/{p['id']}").status_code == 204
    assert client.get("/api/facturas").json() == []
