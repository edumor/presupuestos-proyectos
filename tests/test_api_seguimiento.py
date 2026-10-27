# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date, timedelta

import pytest


@pytest.fixture()
def base(client):
    """Cotización, una persona autónoma (ARS 50/h) y un cliente."""
    client.post("/api/cotizaciones", json={"fecha": "2020-01-01", "moneda": "EUR", "valor": 1.0})
    rol = client.post("/api/roles", json={"nombre": "Diseño"}).json()
    per = client.post("/api/personas", json={"nombre": "Ana", "rol_id": rol["id"], "tipo": "autonomo",
                                              "moneda": "ARS", "tarifa_hora": 50}).json()
    cfg = client.get("/api/config").json()
    cfg["horas_autonomos_anuales"] = 0  # sin estructura: costo/hora = 50 exacto
    client.put("/api/config", json=cfg)
    cli = client.post("/api/clientes", json={"nombre": "Cliente"}).json()
    return client, per, cli


def _proyecto(client, cli, ini, fin, precio=2000, plantilla=True):
    return client.post("/api/proyectos", json={"cliente_id": cli["id"], "nombre": "P", "fecha_inicio": str(ini),
                                                "fecha_fin": str(fin), "precio_base": precio,
                                                "usar_plantilla": plantilla}).json()


def test_plantilla_genera_etapas_con_fechas(base):
    client, _, cli = base
    ini = date(2026, 1, 1)
    p = _proyecto(client, cli, ini, ini + timedelta(days=99))
    es = client.get(f"/api/proyectos/{p['id']}/etapas").json()
    assert [e["nombre"] for e in es] == ["Inicio", "Planificación", "Ejecución", "Cierre"]
    assert es[0]["inicio_previsto"] == str(ini)
    assert es[-1]["fin_previsto"] == str(ini + timedelta(days=99))
    assert sum(e["peso"] for e in es) == pytest.approx(1.0)
    for a, b in zip(es, es[1:]):  # etapas consecutivas, sin huecos
        assert date.fromisoformat(b["inicio_previsto"]) == date.fromisoformat(a["fin_previsto"]) + timedelta(days=1)


def test_evm_y_avance_ponderado(base):
    client, per, cli = base
    hoy = date.today()
    ini = hoy - timedelta(days=9)  # tarea de 20 días: a hoy debería estar el 50%
    p = _proyecto(client, cli, ini, ini + timedelta(days=19), plantilla=False)
    t = client.post(f"/api/proyectos/{p['id']}/tareas", json={
        "nombre": "Diseño", "persona_id": per["id"], "fecha_inicio": str(ini),
        "fecha_fin": str(ini + timedelta(days=19)), "horas_previstas": 20}).json()
    assert t["costo_previsto_base"] == pytest.approx(1000)
    # 12 horas reales (ARS 600) y avance manual 40%
    client.post("/api/horas", json={"tarea_id": t["id"], "persona_id": per["id"], "fecha": str(hoy - timedelta(days=1)), "horas": 12})
    client.patch(f"/api/tareas/{t['id']}/avance", params={"avance": 0.4})
    s = client.get(f"/api/proyectos/{p['id']}/seguimiento").json()
    assert s["bac"] == pytest.approx(1000)
    assert s["pv"] == pytest.approx(500)
    assert s["ev"] == pytest.approx(400)
    assert s["ac"] == pytest.approx(600)
    assert s["cpi"] == pytest.approx(400 / 600)
    assert s["spi"] == pytest.approx(0.8)
    assert s["eac"] == pytest.approx(1500)
    assert s["margen_proyectado"] == pytest.approx((2000 - 1500) / 2000)
    assert s["avance_ponderado"] == pytest.approx(0.4)


def test_avance_automatico_por_horas(base):
    client, per, cli = base
    hoy = date.today()
    p = _proyecto(client, cli, hoy - timedelta(days=5), hoy + timedelta(days=5), plantilla=False)
    t = client.post(f"/api/proyectos/{p['id']}/tareas", json={
        "nombre": "X", "persona_id": per["id"], "fecha_inicio": str(hoy - timedelta(days=5)),
        "fecha_fin": str(hoy + timedelta(days=5)), "horas_previstas": 10}).json()
    client.post("/api/horas", json={"tarea_id": t["id"], "persona_id": per["id"], "fecha": str(hoy), "horas": 3})
    tareas = client.get(f"/api/proyectos/{p['id']}/tareas").json()
    assert tareas[0]["avance"] is None and tareas[0]["avance_efectivo"] == pytest.approx(0.3)


def test_pesos_de_etapas(base):
    client, per, cli = base
    hoy = date.today()
    p = _proyecto(client, cli, hoy - timedelta(days=10), hoy + timedelta(days=10), plantilla=False)
    e1 = client.post(f"/api/proyectos/{p['id']}/etapas", json={"nombre": "A", "peso": 0.25, "orden": 0}).json()
    e2 = client.post(f"/api/proyectos/{p['id']}/etapas", json={"nombre": "B", "peso": 0.75, "orden": 1}).json()
    for e, av in ((e1, 1.0), (e2, 0.2)):
        t = client.post(f"/api/proyectos/{p['id']}/tareas", json={
            "nombre": e["nombre"], "etapa_id": e["id"], "persona_id": per["id"], "fecha_inicio": str(hoy),
            "fecha_fin": str(hoy), "horas_previstas": 10, "avance": av}).json()
    s = client.get(f"/api/proyectos/{p['id']}/seguimiento").json()
    assert s["avance_ponderado"] == pytest.approx(0.25 * 1.0 + 0.75 * 0.2)


def test_costo_congelado_en_la_tarea(base):
    client, per, cli = base
    hoy = date.today()
    p = _proyecto(client, cli, hoy, hoy + timedelta(days=5), plantilla=False)
    t = client.post(f"/api/proyectos/{p['id']}/tareas", json={
        "nombre": "X", "persona_id": per["id"], "fecha_inicio": str(hoy), "fecha_fin": str(hoy), "horas_previstas": 10}).json()
    # sube la tarifa de la persona
    datos = {**per, "tarifa_hora": 80}
    client.put(f"/api/personas/{per['id']}", json=datos)
    t2 = client.put(f"/api/tareas/{t['id']}", json={
        "nombre": "X renombrada", "persona_id": per["id"], "fecha_inicio": str(hoy), "fecha_fin": str(hoy), "horas_previstas": 10}).json()
    assert t2["costo_previsto_base"] == pytest.approx(500)  # mantiene ARS 50/h


def test_tarea_sin_responsable_ni_costo(base):
    client, _, cli = base
    p = _proyecto(client, cli, date.today(), date.today(), plantilla=False)
    r = client.post(f"/api/proyectos/{p['id']}/tareas", json={
        "nombre": "X", "fecha_inicio": str(date.today()), "fecha_fin": str(date.today()), "horas_previstas": 5})
    assert r.status_code == 422


def test_gastos_y_eac(base):
    client, per, cli = base
    p = _proyecto(client, cli, date.today(), date.today(), plantilla=False)
    client.post(f"/api/proyectos/{p['id']}/gastos", json={"concepto": "Imágenes", "importe": 100, "fecha": str(date.today())})
    client.post(f"/api/proyectos/{p['id']}/gastos", json={"concepto": "Imágenes", "importe": 150, "es_real": True,
                                                           "moneda": "EUR", "fecha": str(date.today())})
    s = client.get(f"/api/proyectos/{p['id']}/seguimiento").json()
    assert s["externos_previstos"] == pytest.approx(100)
    assert s["externos_reales"] == pytest.approx(150)  # 1 EUR = 1 ARS en este test
    assert s["eac"] == pytest.approx(150)


def test_ejemplo_y_exportaciones(client):
    client.post("/api/ejemplo")
    cart = client.get("/api/dashboard/cartera").json()
    assert cart["resumen"]["activos"] == 3  # incluye el proyecto en presupuesto
    camp = next(p for p in cart["proyectos"] if p["nombre"] == "Campaña de lanzamiento")
    assert camp["cpi"] < 1 and camp["spi"] < 1  # el ejemplo está pensado con sobrecosto y atraso
    for url in ("/api/export/proyecto/%d" % camp["proyecto_id"], "/api/export/cartera", "/api/export/base"):
        r = client.get(url)
        assert r.status_code == 200 and r.content[:2] == b"PK"
    eq = client.get("/api/dashboard/equipo").json()
    assert eq["personas"] and len(eq["personas"][0]["semanas"]) == 13
    client.delete("/api/ejemplo")
    assert client.get("/api/proyectos").json() == []


def test_volver_a_avance_automatico(base):
    client, per, cli = base
    hoy = date.today()
    p = _proyecto(client, cli, hoy - timedelta(days=5), hoy + timedelta(days=5), plantilla=False)
    t = client.post(f"/api/proyectos/{p['id']}/tareas", json={
        "nombre": "X", "persona_id": per["id"], "fecha_inicio": str(hoy - timedelta(days=5)),
        "fecha_fin": str(hoy + timedelta(days=5)), "horas_previstas": 10}).json()
    client.post("/api/horas", json={"tarea_id": t["id"], "persona_id": per["id"], "fecha": str(hoy), "horas": 2})
    client.patch(f"/api/tareas/{t['id']}/avance", params={"avance": 0.7})
    assert client.get(f"/api/proyectos/{p['id']}/tareas").json()[0]["avance_efectivo"] == pytest.approx(0.7)
    assert client.patch(f"/api/tareas/{t['id']}/avance").status_code == 200  # sin valor = automático
    assert client.get(f"/api/proyectos/{p['id']}/tareas").json()[0]["avance_efectivo"] == pytest.approx(0.2)
