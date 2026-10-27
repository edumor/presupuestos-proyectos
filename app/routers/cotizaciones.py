# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import bcra, costeo
from ..database import get_db
from ..models import Cotizacion, IndiceIPC
from ..schemas import MONEDAS, CotizacionIn, CotizacionOut, IPCIn, IPCOut

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


# ---------- Importación desde el BCRA (opcional, a pedido) ----------
@router.post("/bcra")
def traer_del_bcra(fecha: date | None = None, db: Session = Depends(get_db)):
    """Carga las cotizaciones oficiales del BCRA de esa fecha para todas las monedas admitidas.

    El BCRA publica pesos por unidad; si la moneda base no es ARS se calcula el cruce."""
    try:
        f, ars = bcra.cotizaciones(fecha)
    except bcra.ErrorBCRA as e:
        raise HTTPException(502, str(e))
    base = costeo.moneda_base(db)
    if base not in ars:
        raise HTTPException(422, f"El BCRA no publica {base}")
    cargadas = []
    for m in MONEDAS:
        if m == base or m not in ars:
            continue
        valor = round(ars[m] / ars[base], 10)
        c = db.scalars(select(Cotizacion).where(Cotizacion.fecha == f, Cotizacion.moneda == m)).first()
        if c is None:
            db.add(Cotizacion(fecha=f, moneda=m, valor=valor))
        else:
            c.valor = valor
        cargadas.append(dict(moneda=m, valor=valor))
    db.commit()
    return {"fecha": f, "fuente": "BCRA", "cotizaciones": cargadas}


ipc_router = APIRouter(prefix="/api/ipc", tags=["Inflación"])


@ipc_router.get("", response_model=list[IPCOut])
def listar_ipc(db: Session = Depends(get_db)):
    return db.scalars(select(IndiceIPC).order_by(IndiceIPC.mes.desc())).all()


@ipc_router.post("", response_model=IPCOut, status_code=201)
def cargar_ipc(d: IPCIn, db: Session = Depends(get_db)):
    mes = d.mes.replace(day=1)
    i = db.scalars(select(IndiceIPC).where(IndiceIPC.mes == mes)).first()
    if i is None:
        i = IndiceIPC(mes=mes, variacion=d.variacion, fuente="manual")
        db.add(i)
    else:
        i.variacion, i.fuente = d.variacion, "manual"
    db.commit()
    return i


@ipc_router.delete("/{iid}", status_code=204)
def borrar_ipc(iid: int, db: Session = Depends(get_db)):
    i = db.get(IndiceIPC, iid)
    if i is None:
        raise HTTPException(404, "Mes inexistente")
    db.delete(i)
    db.commit()


@ipc_router.post("/bcra")
def ipc_del_bcra(desde: date = date(2017, 1, 1), db: Session = Depends(get_db)):
    """Trae del BCRA la inflación mensual (IPC INDEC) y actualiza los meses publicados."""
    try:
        datos = bcra.inflacion_mensual(desde)
    except bcra.ErrorBCRA as e:
        raise HTTPException(502, str(e))
    existentes = {i.mes: i for i in db.scalars(select(IndiceIPC))}
    for mes, v in datos.items():
        if mes in existentes:
            existentes[mes].variacion, existentes[mes].fuente = v, "BCRA"
        else:
            db.add(IndiceIPC(mes=mes, variacion=v, fuente="BCRA"))
    db.commit()
    ultimo = max(datos)
    return {"meses": len(datos), "ultimo_mes": ultimo, "ultima_variacion": datos[ultimo]}
