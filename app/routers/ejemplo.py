# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import ejemplo
from ..database import get_db

router = APIRouter(prefix="/api/ejemplo", tags=["Datos de ejemplo"])


@router.get("")
def estado(db: Session = Depends(get_db)):
    return {"cargado": ejemplo.hay_ejemplo(db)}


@router.post("")
def cargar(db: Session = Depends(get_db)):
    try:
        ejemplo.cargar(db)
    except ejemplo.BaseNoCompatible as e:
        raise HTTPException(409, str(e))
    return {"cargado": True}


@router.delete("")
def borrar(db: Session = Depends(get_db)):
    ejemplo.borrar(db)
    return {"cargado": False}
