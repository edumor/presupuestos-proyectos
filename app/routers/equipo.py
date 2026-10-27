# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import costeo
from ..database import get_db
from ..models import Persona, PresupuestoItem, Rol
from ..schemas import CostoHoraOut, PersonaIn, PersonaOut, RolIn, RolOut

router = APIRouter(prefix="/api", tags=["Equipo"])


# --- Roles ---
@router.get("/roles", response_model=list[RolOut])
def roles(db: Session = Depends(get_db)):
    return db.scalars(select(Rol).order_by(Rol.nombre)).all()


@router.post("/roles", response_model=RolOut, status_code=201)
def crear_rol(datos: RolIn, db: Session = Depends(get_db)):
    r = Rol(**datos.model_dump())
    db.add(r)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un rol con ese nombre")
    return r


@router.put("/roles/{rid}", response_model=RolOut)
def editar_rol(rid: int, datos: RolIn, db: Session = Depends(get_db)):
    r = db.get(Rol, rid) or _404("Rol")
    r.nombre, r.descripcion = datos.nombre, datos.descripcion
    db.commit()
    return r


@router.delete("/roles/{rid}", status_code=204)
def borrar_rol(rid: int, db: Session = Depends(get_db)):
    r = db.get(Rol, rid) or _404("Rol")
    if db.scalars(select(Persona).where(Persona.rol_id == rid)).first():
        raise HTTPException(409, "Hay personas con ese rol; cambiales el rol primero")
    db.delete(r)
    db.commit()


# --- Personas ---
def _persona_out(p: Persona) -> PersonaOut:
    o = PersonaOut.model_validate(p)
    o.rol_nombre = p.rol.nombre if p.rol else None
    return o


@router.get("/personas", response_model=list[PersonaOut])
def personas(solo_activas: bool = False, db: Session = Depends(get_db)):
    q = select(Persona).order_by(Persona.nombre)
    if solo_activas:
        q = q.where(Persona.activo)
    return [_persona_out(p) for p in db.scalars(q)]


@router.post("/personas", response_model=PersonaOut, status_code=201)
def crear_persona(datos: PersonaIn, db: Session = Depends(get_db)):
    db.get(Rol, datos.rol_id) or _404("Rol")
    p = Persona(**datos.model_dump())
    db.add(p)
    db.commit()
    return _persona_out(p)


@router.put("/personas/{pid}", response_model=PersonaOut)
def editar_persona(pid: int, datos: PersonaIn, db: Session = Depends(get_db)):
    p = db.get(Persona, pid) or _404("Persona")
    for k, v in datos.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return _persona_out(p)


@router.delete("/personas/{pid}", status_code=204)
def borrar_persona(pid: int, db: Session = Depends(get_db)):
    p = db.get(Persona, pid) or _404("Persona")
    if db.scalars(select(PresupuestoItem).where(PresupuestoItem.persona_id == pid)).first():
        raise HTTPException(409, "La persona figura en presupuestos; desactivala en lugar de borrarla")
    db.delete(p)
    db.commit()


@router.get("/personas/{pid}/costo-hora", response_model=CostoHoraOut)
def costo_hora(pid: int, db: Session = Depends(get_db)):
    p = db.get(Persona, pid) or _404("Persona")
    return costeo.costo_hora(db, p)


@router.get("/costos-hora", response_model=list[CostoHoraOut])
def costos_hora(db: Session = Depends(get_db)):
    """Costo por hora de todas las personas activas (una sola tasa de estructura)."""
    tasa = costeo.estructura(db)["tasa_estructura_base"]
    ps = db.scalars(select(Persona).where(Persona.activo).order_by(Persona.nombre))
    return [costeo.costo_hora(db, p, tasa=tasa) for p in ps]


def _404(que: str):
    raise HTTPException(404, f"{que} inexistente")
