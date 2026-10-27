# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import costeo
from ..database import get_db
from ..models import HoraReal, Persona, Tarea
from ..schemas import HoraIn, HoraOut

router = APIRouter(prefix="/api/horas", tags=["Horas"])


def _out(h: HoraReal) -> HoraOut:
    o = HoraOut.model_validate(h)
    t = h.tarea
    o.tarea_nombre = t.nombre
    o.proyecto_id = t.proyecto_id
    o.proyecto_nombre = t.proyecto.nombre
    return o


@router.get("", response_model=list[HoraOut])
def listar(proyecto_id: int | None = None, persona_id: int | None = None,
           desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    q = select(HoraReal).join(Tarea).order_by(HoraReal.fecha.desc(), HoraReal.id.desc())
    if proyecto_id:
        q = q.where(Tarea.proyecto_id == proyecto_id)
    if persona_id:
        q = q.where(HoraReal.persona_id == persona_id)
    if desde:
        q = q.where(HoraReal.fecha >= desde)
    if hasta:
        q = q.where(HoraReal.fecha <= hasta)
    personas = {p.id: p.nombre for p in db.scalars(select(Persona))}
    out = []
    for h in db.scalars(q).all():
        o = _out(h)
        o.persona_nombre = personas.get(h.persona_id)
        out.append(o)
    return out


def _guardar(db: Session, h: HoraReal, d: HoraIn) -> None:
    if db.get(Tarea, d.tarea_id) is None:
        raise HTTPException(404, "Tarea inexistente")
    per = db.get(Persona, d.persona_id)
    if per is None:
        raise HTTPException(404, "Persona inexistente")
    for k, v in d.model_dump().items():
        setattr(h, k, v)
    # costo real = costo/hora de la persona a la fecha trabajada (con la cotización de ese día)
    h.costo_hora_base = round(costeo.costo_hora(db, per, d.fecha)["costo_total_base"], 2)


@router.post("", response_model=HoraOut, status_code=201)
def cargar(d: HoraIn, db: Session = Depends(get_db)):
    h = HoraReal()
    _guardar(db, h, d)
    db.add(h); db.commit()
    return _out(h)


@router.post("/lote", response_model=list[HoraOut], status_code=201)
def cargar_lote(items: list[HoraIn], db: Session = Depends(get_db)):
    """Carga varias horas juntas (planilla semanal)."""
    hs = []
    for d in items:
        h = HoraReal()
        _guardar(db, h, d)
        db.add(h); hs.append(h)
    db.commit()
    return [_out(h) for h in hs]


@router.put("/{hid}", response_model=HoraOut)
def editar(hid: int, d: HoraIn, db: Session = Depends(get_db)):
    h = db.get(HoraReal, hid)
    if h is None:
        raise HTTPException(404, "Registro inexistente")
    _guardar(db, h, d); db.commit()
    return _out(h)


@router.delete("/{hid}", status_code=204)
def borrar(hid: int, db: Session = Depends(get_db)):
    h = db.get(HoraReal, hid)
    if h is None:
        raise HTTPException(404, "Registro inexistente")
    db.delete(h); db.commit()
