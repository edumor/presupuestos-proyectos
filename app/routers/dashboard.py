# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import costeo, seguimiento
from ..database import get_db
from ..models import Proyecto

router = APIRouter(prefix="/api", tags=["Dashboards"])


@router.get("/proyectos/{pid}/seguimiento")
def seguimiento_proyecto(pid: int, fecha: date | None = None, db: Session = Depends(get_db)):
    p = db.get(Proyecto, pid)
    if p is None:
        raise HTTPException(404, "Proyecto inexistente")
    hoy = fecha or date.today()
    m = seguimiento.metricas(db, p, hoy)
    m["curva_s"] = seguimiento.curva_s(db, p, hoy)
    m["por_persona"] = seguimiento.costo_por_persona(p, hoy)
    m["margen_alerta"] = costeo.config(db).margen_alerta
    return m


@router.get("/dashboard/cartera")
def cartera(incluir_terminados: bool = False, db: Session = Depends(get_db)):
    q = select(Proyecto).order_by(Proyecto.fecha_inicio)
    proys = db.scalars(q).all() if incluir_terminados else seguimiento.proyectos_activos(db)
    filas = []
    for p in proys:
        m = seguimiento.metricas(db, p)
        m.pop("etapas")
        filas.append(m)
    con_precio = [f for f in filas if f["precio_base"]]
    tot_precio = sum(f["precio_base"] for f in con_precio)
    return dict(
        proyectos=filas,
        resumen=dict(
            activos=len(filas),
            facturacion_base=tot_precio,
            costo_real_base=sum(f["ac"] + f["externos_reales"] for f in filas),
            margen_previsto=(sum(f["precio_base"] - f["costo_previsto"] for f in con_precio) / tot_precio) if tot_precio else None,
            margen_proyectado=(sum(f["precio_base"] - f["eac"] for f in con_precio) / tot_precio) if tot_precio else None,
            en_riesgo=sum(1 for f in filas if (f["cpi"] or 1) < 0.9 or (f["spi"] or 1) < 0.9),
            etapas_atrasadas=sum(f["etapas_atrasadas"] for f in filas),
        ),
        margen_alerta=costeo.config(db).margen_alerta,
    )


@router.get("/dashboard/equipo")
def equipo(semanas_atras: int = 6, semanas_adelante: int = 6, db: Session = Depends(get_db)):
    cfg = costeo.config(db)
    desde = date.today() - timedelta(weeks=semanas_atras)
    return dict(
        horas_semana_empleado=cfg.horas_anuales / 52,
        personas=seguimiento.carga_equipo(db, desde, semanas_atras + semanas_adelante + 1, cfg.horas_anuales / 52),
    )
