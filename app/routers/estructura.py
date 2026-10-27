# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import costeo
from ..database import get_db
from ..models import CostoFijo
from ..schemas import CostoFijoIn, CostoFijoOut, TasaEstructuraOut

router = APIRouter(prefix="/api", tags=["Estructura"])


def _out(db: Session, c: CostoFijo) -> CostoFijoOut:
    o = CostoFijoOut.model_validate(c)
    try:
        o.anual_base = costeo.costo_fijo_anual_base(db, c)
    except costeo.FaltaCotizacion:
        o.anual_base = None
    return o


@router.get("/costos-fijos", response_model=list[CostoFijoOut])
def listar(db: Session = Depends(get_db)):
    return [_out(db, c) for c in db.scalars(select(CostoFijo).order_by(CostoFijo.concepto))]


@router.post("/costos-fijos", response_model=CostoFijoOut, status_code=201)
def crear(datos: CostoFijoIn, db: Session = Depends(get_db)):
    c = CostoFijo(**datos.model_dump())
    db.add(c)
    db.commit()
    return _out(db, c)


@router.put("/costos-fijos/{cid}", response_model=CostoFijoOut)
def editar(cid: int, datos: CostoFijoIn, db: Session = Depends(get_db)):
    c = db.get(CostoFijo, cid)
    if c is None:
        raise HTTPException(404, "Costo fijo inexistente")
    for k, v in datos.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return _out(db, c)


@router.delete("/costos-fijos/{cid}", status_code=204)
def borrar(cid: int, db: Session = Depends(get_db)):
    c = db.get(CostoFijo, cid)
    if c is None:
        raise HTTPException(404, "Costo fijo inexistente")
    db.delete(c)
    db.commit()


@router.get("/tasa-estructura", response_model=TasaEstructuraOut)
def tasa(db: Session = Depends(get_db)):
    return costeo.estructura(db)
