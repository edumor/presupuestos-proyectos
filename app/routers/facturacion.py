# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Facturas y cobros (registro interno)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import contratos, costeo, facturacion
from ..database import get_db
from ..models import Cobro, Etapa, Factura, Proyecto
from ..schemas import CobroIn, FacturaIn, FacturaOut

router = APIRouter(prefix="/api", tags=["Facturación"])


def _out(f: Factura, hoy: date | None = None) -> FacturaOut:
    o = FacturaOut.model_validate(f)
    for k, v in facturacion.resumen(f, hoy).items():
        setattr(o, k, v)
    o.proyecto_nombre = f.proyecto.nombre
    o.cliente_nombre = f.proyecto.cliente.nombre if f.proyecto.cliente else None
    if f.etapa_id:
        e = next((e for e in f.proyecto.etapas if e.id == f.etapa_id), None)
        o.etapa_nombre = e.nombre if e else None
    for c, co in zip(f.cobros, o.cobros):
        co.diferencia_cambio = facturacion.diferencia_cambio(c)
    return o


def _get(db: Session, modelo, id_: int, nombre: str):
    x = db.get(modelo, id_)
    if x is None:
        raise HTTPException(404, f"{nombre} inexistente")
    return x


def _cotizacion(db: Session, moneda: str, fecha: date, manual: float | None) -> float:
    if moneda == costeo.moneda_base(db):
        return 1.0
    return float(manual) if manual else costeo.base_por_unidad(db, moneda, fecha)


def _guardar(db: Session, f: Factura, p: Proyecto, d: FacturaIn) -> None:
    if d.etapa_id is not None:
        e = db.get(Etapa, d.etapa_id)
        if e is None or e.proyecto_id != p.id:
            raise HTTPException(422, "La etapa no pertenece al proyecto")
    datos = d.model_dump(exclude={"cotizacion", "moneda"})
    for k, v in datos.items():
        setattr(f, k, v)
    f.moneda = d.moneda or p.moneda_contrato or costeo.moneda_base(db)
    f.cotizacion = _cotizacion(db, f.moneda, d.fecha, d.cotizacion)
    f.neto_base = round(d.importe_neto * f.cotizacion, 2)
    if f.cobros and facturacion.cobrado(f) > facturacion.total(f) + facturacion.TOLERANCIA:
        raise HTTPException(422, "El total no puede quedar por debajo de lo ya cobrado")


@router.get("/facturas", response_model=list[FacturaOut])
def listar(desde: date | None = None, hasta: date | None = None, estado: str | None = None,
           cliente_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Factura).join(Proyecto).order_by(Factura.fecha.desc(), Factura.id.desc())
    if desde:
        q = q.where(Factura.fecha >= desde)
    if hasta:
        q = q.where(Factura.fecha <= hasta)
    if cliente_id:
        q = q.where(Proyecto.cliente_id == cliente_id)
    out = [_out(f) for f in db.scalars(q)]
    if estado == "a_cobrar":
        return [o for o in out if o.saldo > 0]
    return [o for o in out if not estado or o.estado == estado]


@router.get("/proyectos/{pid}/facturas")
def de_proyecto(pid: int, db: Session = Depends(get_db)):
    """Facturas del proyecto y resumen en la moneda del contrato."""
    p = _get(db, Proyecto, pid, "Proyecto")
    fs = db.scalars(select(Factura).where(Factura.proyecto_id == pid).order_by(Factura.fecha, Factura.id)).all()
    base = costeo.moneda_base(db)
    moneda = p.moneda_contrato or base
    contrato = contratos.precio_actual(db, p)
    precio = contrato.get("precio_contrato") if moneda != base else contrato["precio"]
    vigentes = [f for f in fs if not f.anulada]
    # lo facturado en otra moneda se lleva a la del contrato con la cotización de la factura
    def en_contrato(importe, f):
        if f.moneda == moneda:
            return importe
        try:
            fx = 1.0 if moneda == base else costeo.base_por_unidad(db, moneda, f.fecha)
        except costeo.FaltaCotizacion:  # sin cotización a esa fecha: la vigente hoy
            fx = costeo.base_por_unidad(db, moneda)
        return importe * float(f.cotizacion) / fx
    facturado = round(sum(en_contrato(float(f.importe_neto), f) for f in vigentes), 2)
    rs = [facturacion.resumen(f) for f in vigentes]
    return dict(
        moneda=moneda, precio=precio, facturado=facturado,
        por_facturar=round(precio - facturado, 2) if precio is not None else None,
        pct_facturado=(facturado / precio) if precio else None,
        cobrado_base=round(sum(float(c.importe_base) for f in vigentes for c in f.cobros), 2),
        saldo_base=round(sum(r["saldo_base"] for r in rs), 2),
        vencido_base=round(sum(r["saldo_base"] for r in rs if r["estado"] == "vencida"), 2),
        diferencia_cambio=round(sum(r["diferencia_cambio"] for r in rs), 2),
        facturas=[_out(f) for f in fs])


@router.post("/proyectos/{pid}/facturas", response_model=FacturaOut, status_code=201)
def crear(pid: int, d: FacturaIn, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    f = Factura(proyecto_id=pid)
    f.cobros = []
    _guardar(db, f, p, d)
    db.add(f); db.commit(); db.refresh(f)
    return _out(f)


@router.put("/facturas/{fid}", response_model=FacturaOut)
def editar(fid: int, d: FacturaIn, db: Session = Depends(get_db)):
    f = _get(db, Factura, fid, "Factura")
    moneda_ant = f.moneda
    _guardar(db, f, f.proyecto, d)
    if f.cobros and f.moneda != moneda_ant:
        raise HTTPException(422, "No se puede cambiar la moneda de una factura con cobros")
    db.commit()
    return _out(f)


@router.delete("/facturas/{fid}", status_code=204)
def borrar(fid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, Factura, fid, "Factura")); db.commit()


@router.post("/facturas/{fid}/cobros", response_model=FacturaOut, status_code=201)
def cobrar(fid: int, d: CobroIn, db: Session = Depends(get_db)):
    f = _get(db, Factura, fid, "Factura")
    if f.anulada:
        raise HTTPException(422, "La factura está anulada")
    if d.fecha < f.fecha:
        raise HTTPException(422, "El cobro no puede ser anterior a la factura")
    saldo = facturacion.total(f) - facturacion.cobrado(f)
    if d.importe > saldo + facturacion.TOLERANCIA:
        raise HTTPException(422, f"El cobro supera el saldo de la factura ({f.moneda} {saldo:,.2f})")
    cot = _cotizacion(db, f.moneda, d.fecha, d.cotizacion)
    f.cobros.append(Cobro(fecha=d.fecha, importe=d.importe, cotizacion=cot,
                          importe_base=round(d.importe * cot, 2), notas=d.notas))
    db.commit(); db.refresh(f)
    return _out(f)


@router.delete("/cobros/{cid}", status_code=204)
def borrar_cobro(cid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, Cobro, cid, "Cobro")); db.commit()

