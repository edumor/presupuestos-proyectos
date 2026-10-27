# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Catálogo de servicios y presupuestos por proyecto (versiones, estados y aprobación)."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import presupuestos as motor
from ..database import get_db
from ..models import (CostoExterno, EstadoPresupuesto, Persona, Presupuesto, PresupuestoItem, Proyecto, Rol,
                      Servicio, Tarea)
from ..schemas import PresupuestoIn, PresupuestoNuevo, ServicioIn, ServicioOut

router = APIRouter(prefix="/api", tags=["Presupuestos"])


def _get(db: Session, modelo, id_: int, que: str):
    obj = db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, f"{que} inexistente")
    return obj


# ---------- Catálogo de servicios ----------
def _serv_out(s: Servicio, roles: dict[int, str]) -> ServicioOut:
    o = ServicioOut.model_validate(s)
    o.rol_nombre = roles.get(s.rol_sugerido_id)
    return o


def _roles(db: Session) -> dict[int, str]:
    return {r.id: r.nombre for r in db.scalars(select(Rol))}


@router.get("/servicios", response_model=list[ServicioOut])
def servicios(solo_activos: bool = False, db: Session = Depends(get_db)):
    q = select(Servicio).order_by(Servicio.nombre)
    if solo_activos:
        q = q.where(Servicio.activo)
    roles = _roles(db)
    return [_serv_out(s, roles) for s in db.scalars(q)]


def _validar_servicio(db: Session, d: ServicioIn) -> None:
    if d.rol_sugerido_id is not None:
        _get(db, Rol, d.rol_sugerido_id, "Rol")
    if not d.horas_sugeridas and not d.pct_sobre_total:
        raise HTTPException(422, "Indicá las horas sugeridas o el % sobre el total")


@router.post("/servicios", response_model=ServicioOut, status_code=201)
def crear_servicio(d: ServicioIn, db: Session = Depends(get_db)):
    _validar_servicio(db, d)
    s = Servicio(**d.model_dump())
    db.add(s)
    db.commit()
    return _serv_out(s, _roles(db))


@router.put("/servicios/{sid}", response_model=ServicioOut)
def editar_servicio(sid: int, d: ServicioIn, db: Session = Depends(get_db)):
    s = _get(db, Servicio, sid, "Servicio")
    _validar_servicio(db, d)
    for k, v in d.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return _serv_out(s, _roles(db))


@router.delete("/servicios/{sid}", status_code=204)
def borrar_servicio(sid: int, db: Session = Depends(get_db)):
    s = _get(db, Servicio, sid, "Servicio")
    if db.scalars(select(PresupuestoItem).where(PresupuestoItem.servicio_id == sid).limit(1)).first():
        s.activo = False  # usado en presupuestos: se desactiva en lugar de borrarse
    else:
        db.delete(s)
    db.commit()


# ---------- Presupuestos ----------
def _detalle(db: Session, pres: Presupuesto) -> dict:
    d = motor.calcular(db, pres)
    p = pres.proyecto
    d.update(proyecto_nombre=p.nombre, cliente_nombre=p.cliente.nombre if p.cliente else None,
             tiene_tareas_generadas=any(t.item_id for t in p.tareas))
    return d


@router.get("/proyectos/{pid}/presupuestos")
def listar(pid: int, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    out = []
    for pres in sorted(p.presupuestos, key=lambda x: x.version):
        try:
            r = motor.calcular(db, pres)["resumen"]
        except Exception:  # p. ej. falta una cotización: la lista igual se muestra
            r = {}
        out.append(dict(id=pres.id, version=pres.version, estado=pres.estado.value, margen=pres.margen,
                        fecha_envio=pres.fecha_envio, fecha_aprobacion=pres.fecha_aprobacion,
                        n_items=len(pres.items), horas=r.get("horas"), costo_total=r.get("costo_total"),
                        precio=r.get("precio"), margen_real=r.get("margen_real")))
    return out


@router.post("/proyectos/{pid}/presupuestos", status_code=201)
def crear(pid: int, d: PresupuestoNuevo, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    base = None
    if d.copiar_de is not None:
        base = _get(db, Presupuesto, d.copiar_de, "Presupuesto")
        if base.proyecto_id != pid:
            raise HTTPException(422, "El presupuesto a copiar es de otro proyecto")
    pres = motor.nueva_version(db, p, base)
    db.commit()
    return _detalle(db, pres)


@router.get("/presupuestos/{prid}")
def detalle(prid: int, db: Session = Depends(get_db)):
    return _detalle(db, _get(db, Presupuesto, prid, "Presupuesto"))


@router.put("/presupuestos/{prid}")
def guardar(prid: int, d: PresupuestoIn, db: Session = Depends(get_db)):
    pres = _get(db, Presupuesto, prid, "Presupuesto")
    if pres.estado != EstadoPresupuesto.borrador:
        raise HTTPException(409, "Solo se puede modificar una versión en borrador. Creá una versión nueva a partir de esta.")
    for it in d.items:
        if it.rol_id is not None:
            _get(db, Rol, it.rol_id, "Rol")
        if it.persona_id is not None:
            _get(db, Persona, it.persona_id, "Persona")
        if it.servicio_id is not None:
            _get(db, Servicio, it.servicio_id, "Servicio")
        if it.fecha_inicio and it.fecha_fin and it.fecha_fin < it.fecha_inicio:
            raise HTTPException(422, f"«{it.tarea}»: la fecha de fin es anterior a la de inicio")
    pres.margen, pres.impuesto, pres.precio_base, pres.notas = d.margen, d.impuesto, d.precio_base, d.notas
    pres.items.clear()
    pres.costos_externos.clear()
    db.flush()
    for i, it in enumerate(d.items):
        pres.items.append(PresupuestoItem(orden=i, **it.model_dump()))
    for g in d.externos:
        pres.costos_externos.append(CostoExterno(concepto=g.concepto, moneda=g.moneda, importe=g.importe,
                                                 cotizacion=1, importe_base=0, es_real=False))
    db.commit()
    db.refresh(pres)
    return _detalle(db, pres)


class CambioEstado(BaseModel):
    estado: Literal["borrador", "enviado", "rechazado"]
    fecha: date | None = None


@router.post("/presupuestos/{prid}/estado")
def cambiar_estado(prid: int, d: CambioEstado, db: Session = Depends(get_db)):
    pres = _get(db, Presupuesto, prid, "Presupuesto")
    if pres.estado == EstadoPresupuesto.aprobado:
        raise HTTPException(409, "Una versión aprobada no cambia de estado")
    pres.estado = EstadoPresupuesto(d.estado)
    if d.estado == "enviado":
        pres.fecha_envio = d.fecha or date.today()
    db.commit()
    return _detalle(db, pres)


class Aprobacion(BaseModel):
    generar_tareas: bool = True
    fecha: date | None = None


@router.post("/presupuestos/{prid}/aprobar")
def aprobar(prid: int, d: Aprobacion, db: Session = Depends(get_db)):
    pres = _get(db, Presupuesto, prid, "Presupuesto")
    try:
        motor.aprobar(db, pres, d.generar_tareas, d.fecha)
    except motor.ErrorPresupuesto as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return _detalle(db, pres)


@router.delete("/presupuestos/{prid}", status_code=204)
def borrar(prid: int, db: Session = Depends(get_db)):
    pres = _get(db, Presupuesto, prid, "Presupuesto")
    if pres.estado == EstadoPresupuesto.aprobado:
        raise HTTPException(409, "No se puede borrar una versión aprobada")
    ids = [i.id for i in pres.items]
    if ids and db.scalars(select(Tarea).where(Tarea.item_id.in_(ids)).limit(1)).first():
        raise HTTPException(409, "Hay tareas generadas desde esta versión")
    db.delete(pres)
    db.commit()
