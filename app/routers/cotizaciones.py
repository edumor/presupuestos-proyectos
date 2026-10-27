# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import costeo
from ..database import get_db
from ..models import Cotizacion
from ..schemas import CotizacionIn, CotizacionOut

router = APIRouter(prefix="/api/cotizaciones", tags=["Cotizaciones"])


def _out(c: Cotizacion) -> CotizacionOut:
    return CotizacionOut(id=c.id, fecha=c.fecha, moneda=c.moneda, valor=float(c.valor),
                         inversa=1 / float(c.valor))


@router.get("", response_model=list[CotizacionOut])
def listar(moneda: str | None = None, limite: int = 120, db: Session = Depends(get_db)):
    q = select(Cotizacion).order_by(Cotizacion.fecha.desc()).limit(limite)
    if moneda:
        q = q.where(Cotizacion.moneda == moneda.upper())
    return [_out(c) for c in db.scalars(q)]


@router.get("/vigente", response_model=CotizacionOut)
def vigente(moneda: str, fecha: date | None = None, db: Session = Depends(get_db)):
    c = costeo.cotizacion_vigente(db, moneda.upper(), fecha)
    if c is None:
        raise HTTPException(404, f"No hay cotización cargada para {moneda.upper()}")
    return _out(c)


@router.post("", response_model=CotizacionOut, status_code=201)
def cargar(datos: CotizacionIn, db: Session = Depends(get_db)):
    """Carga o reemplaza la cotización de esa moneda en esa fecha (1 moneda = valor en moneda base)."""
    if datos.moneda == costeo.moneda_base(db):
        raise HTTPException(422, f"{datos.moneda} es la moneda base: no necesita cotización")
    c = db.scalars(select(Cotizacion).where(Cotizacion.fecha == datos.fecha,
                                            Cotizacion.moneda == datos.moneda)).first()
    if c is None:
        c = Cotizacion(**datos.model_dump())
        db.add(c)
    else:
        c.valor = datos.valor
    db.commit()
    return _out(c)


@router.delete("/{cid}", status_code=204)
def borrar(cid: int, db: Session = Depends(get_db)):
    c = db.get(Cotizacion, cid)
    if c is None:
        raise HTTPException(404, "Cotización inexistente")
    db.delete(c)
    db.commit()
