# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import costeo, seguimiento
from ..database import get_db
from ..models import (Cliente, CostoExterno, Etapa, EstadoProyecto, PlantillaEtapa, Persona,
                      Proyecto, Tarea)
from ..schemas import (ClienteIn, ClienteOut, EtapaIn, EtapaOut, GastoIn, GastoOut,
                       PlantillaEtapaIn, PlantillaEtapaOut, ProyectoCrear, ProyectoIn, ProyectoOut,
                       TareaIn, TareaOut)

router = APIRouter(prefix="/api", tags=["Proyectos"])


def _get(db: Session, modelo, id_: int, que: str):
    obj = db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, f"{que} inexistente")
    return obj


# ---------- Clientes ----------
@router.get("/clientes", response_model=list[ClienteOut])
def clientes(db: Session = Depends(get_db)):
    return db.scalars(select(Cliente).order_by(Cliente.nombre)).all()


@router.post("/clientes", response_model=ClienteOut, status_code=201)
def crear_cliente(d: ClienteIn, db: Session = Depends(get_db)):
    c = Cliente(**d.model_dump())
    db.add(c); db.commit()
    return c


@router.put("/clientes/{cid}", response_model=ClienteOut)
def editar_cliente(cid: int, d: ClienteIn, db: Session = Depends(get_db)):
    c = _get(db, Cliente, cid, "Cliente")
    for k, v in d.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return c


@router.delete("/clientes/{cid}", status_code=204)
def borrar_cliente(cid: int, db: Session = Depends(get_db)):
    c = _get(db, Cliente, cid, "Cliente")
    if db.scalars(select(Proyecto).where(Proyecto.cliente_id == cid)).first():
        raise HTTPException(409, "El cliente tiene proyectos")
    db.delete(c); db.commit()


# ---------- Plantilla de etapas ----------
@router.get("/plantilla-etapas", response_model=list[PlantillaEtapaOut])
def plantilla(db: Session = Depends(get_db)):
    return db.scalars(select(PlantillaEtapa).order_by(PlantillaEtapa.orden)).all()


@router.put("/plantilla-etapas", response_model=list[PlantillaEtapaOut])
def guardar_plantilla(etapas: list[PlantillaEtapaIn], db: Session = Depends(get_db)):
    """Reemplaza la plantilla completa (no afecta proyectos existentes)."""
    for e in db.scalars(select(PlantillaEtapa)).all():
        db.delete(e)
    for i, e in enumerate(etapas):
        db.add(PlantillaEtapa(**{**e.model_dump(), "orden": i}))
    db.commit()
    return plantilla(db)


# ---------- Proyectos ----------
def _proy_out(p: Proyecto) -> ProyectoOut:
    o = ProyectoOut.model_validate(p)
    o.cliente_nombre = p.cliente.nombre if p.cliente else None
    return o


def _normalizar_contrato(db: Session, p: Proyecto) -> None:
    """Contrato en otra moneda: guarda también su equivalente en moneda base a hoy como referencia."""
    base = costeo.moneda_base(db)
    if not p.moneda_contrato or p.moneda_contrato == base:
        p.moneda_contrato, p.precio_contrato = None, None
        return
    if p.precio_contrato is not None:
        p.precio_base = round(float(p.precio_contrato) * costeo.base_por_unidad(db, p.moneda_contrato), 2)
    if p.ajuste_indice:
        raise HTTPException(422, "El ajuste por IPC es para contratos en la moneda base")


@router.get("/proyectos", response_model=list[ProyectoOut])
def proyectos(estado: EstadoProyecto | None = None, db: Session = Depends(get_db)):
    q = select(Proyecto).order_by(Proyecto.fecha_inicio.desc())
    if estado:
        q = q.where(Proyecto.estado == estado)
    return [_proy_out(p) for p in db.scalars(q)]


@router.post("/proyectos", response_model=ProyectoOut, status_code=201)
def crear_proyecto(d: ProyectoCrear, db: Session = Depends(get_db)):
    _get(db, Cliente, d.cliente_id, "Cliente")
    datos = d.model_dump(exclude={"usar_plantilla"})
    p = Proyecto(**datos)
    _normalizar_contrato(db, p)
    db.add(p)
    if d.usar_plantilla:
        p.etapas = seguimiento.etapas_desde_plantilla(db, p)
    db.commit()
    return _proy_out(p)


@router.get("/proyectos/{pid}", response_model=ProyectoOut)
def proyecto(pid: int, db: Session = Depends(get_db)):
    return _proy_out(_get(db, Proyecto, pid, "Proyecto"))


@router.put("/proyectos/{pid}", response_model=ProyectoOut)
def editar_proyecto(pid: int, d: ProyectoIn, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    for k, v in d.model_dump().items():
        setattr(p, k, v)
    _normalizar_contrato(db, p)
    db.commit()
    return _proy_out(p)


@router.delete("/proyectos/{pid}", status_code=204)
def borrar_proyecto(pid: int, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    for g in db.scalars(select(CostoExterno).where(CostoExterno.proyecto_id == pid)):
        db.delete(g)
    for t in list(p.tareas):  # primero las tareas: pueden apuntar a ítems de presupuesto
        db.delete(t)
    db.flush()
    db.expire(p, ["tareas"])
    db.delete(p); db.commit()


# ---------- Etapas ----------
@router.get("/proyectos/{pid}/etapas", response_model=list[EtapaOut])
def etapas(pid: int, db: Session = Depends(get_db)):
    return _get(db, Proyecto, pid, "Proyecto").etapas


@router.post("/proyectos/{pid}/etapas", response_model=EtapaOut, status_code=201)
def crear_etapa(pid: int, d: EtapaIn, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    e = Etapa(**d.model_dump())
    p.etapas.append(e); db.commit()
    return e


@router.put("/etapas/{eid}", response_model=EtapaOut)
def editar_etapa(eid: int, d: EtapaIn, db: Session = Depends(get_db)):
    e = _get(db, Etapa, eid, "Etapa")
    for k, v in d.model_dump().items():
        setattr(e, k, v)
    if e.aprobada_cliente and not e.fecha_aprobacion:
        e.fecha_aprobacion = date.today()
    db.commit()
    return e


@router.delete("/etapas/{eid}", status_code=204)
def borrar_etapa(eid: int, db: Session = Depends(get_db)):
    e = _get(db, Etapa, eid, "Etapa")
    for t in e.tareas:
        t.etapa_id = None
    db.delete(e); db.commit()


# ---------- Tareas ----------
def _tarea_out(t: Tarea, hoy: date | None = None) -> TareaOut:
    hoy = hoy or date.today()
    o = TareaOut.model_validate(t)
    o.persona_nombre = t.persona.nombre if t.persona else None
    o.horas_reales = sum(h.horas for h in t.horas)
    o.costo_real_base = sum(h.horas * float(h.costo_hora_base) for h in t.horas)
    o.avance_efectivo = seguimiento.avance_tarea(t, hoy)
    return o


def _aplicar_tarea(db: Session, t: Tarea, d: TareaIn) -> None:
    persona_antes, costo_antes = t.persona_id, t.costo_hora_base
    datos = d.model_dump(exclude={"avance", "costo_hora_base"})
    for k, v in datos.items():
        setattr(t, k, v)
    if d.etapa_id is not None:
        e = _get(db, Etapa, d.etapa_id, "Etapa")
        if e.proyecto_id != t.proyecto_id:
            raise HTTPException(422, "La etapa es de otro proyecto")
    costo = d.costo_hora_base
    if costo is None and d.persona_id is not None:
        per = _get(db, Persona, d.persona_id, "Persona")
        # se conserva el costo congelado si el responsable no cambió
        costo = float(costo_antes) if (t.id and costo_antes and persona_antes == d.persona_id) else \
            round(costeo.costo_hora(db, per)["costo_total_base"], 2)
    if costo is None:
        raise HTTPException(422, "Elegí un responsable o cargá el costo por hora de la tarea")
    t.costo_hora_base = costo
    t.costo_previsto_base = round(costo * d.horas_previstas, 2)
    if d.avance != t.avance:
        seguimiento.registrar_avance(db, t, d.avance)


@router.get("/proyectos/{pid}/tareas", response_model=list[TareaOut])
def tareas(pid: int, db: Session = Depends(get_db)):
    p = _get(db, Proyecto, pid, "Proyecto")
    return [_tarea_out(t) for t in sorted(p.tareas, key=lambda t: (t.fecha_inicio, t.orden))]


@router.post("/proyectos/{pid}/tareas", response_model=TareaOut, status_code=201)
def crear_tarea(pid: int, d: TareaIn, db: Session = Depends(get_db)):
    _get(db, Proyecto, pid, "Proyecto")
    t = Tarea(proyecto_id=pid, nombre=d.nombre, fecha_inicio=d.fecha_inicio, fecha_fin=d.fecha_fin,
              horas_previstas=d.horas_previstas, costo_previsto_base=0)
    db.add(t)
    _aplicar_tarea(db, t, d)
    db.commit()
    return _tarea_out(t)


@router.put("/tareas/{tid}", response_model=TareaOut)
def editar_tarea(tid: int, d: TareaIn, db: Session = Depends(get_db)):
    t = _get(db, Tarea, tid, "Tarea")
    _aplicar_tarea(db, t, d)
    db.commit()
    return _tarea_out(t)


@router.patch("/tareas/{tid}/avance", response_model=TareaOut)
def avance(tid: int, avance: float | None = None, fecha: date | None = None, db: Session = Depends(get_db)):
    """Actualiza solo el % de avance (0..1) y lo registra en el historial."""
    if avance is not None and not 0 <= avance <= 1:
        raise HTTPException(422, "El avance va de 0 a 1")
    t = _get(db, Tarea, tid, "Tarea")
    seguimiento.registrar_avance(db, t, avance, fecha)
    if avance == 1 and not t.fin_real:
        t.fin_real = fecha or date.today()
    db.commit()
    return _tarea_out(t)


@router.delete("/tareas/{tid}", status_code=204)
def borrar_tarea(tid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, Tarea, tid, "Tarea")); db.commit()


# ---------- Gastos externos del proyecto ----------
@router.get("/proyectos/{pid}/gastos", response_model=list[GastoOut])
def listar_gastos(pid: int, db: Session = Depends(get_db)):
    _get(db, Proyecto, pid, "Proyecto")
    return db.scalars(select(CostoExterno).where(CostoExterno.proyecto_id == pid)
                      .order_by(CostoExterno.es_real, CostoExterno.fecha)).all()


@router.post("/proyectos/{pid}/gastos", response_model=GastoOut, status_code=201)
def crear_gasto(pid: int, d: GastoIn, db: Session = Depends(get_db)):
    _get(db, Proyecto, pid, "Proyecto")
    fx = costeo.base_por_unidad(db, d.moneda, d.fecha)
    g = CostoExterno(proyecto_id=pid, **d.model_dump(), cotizacion=fx, importe_base=round(d.importe * fx, 2))
    db.add(g); db.commit()
    return g


@router.delete("/gastos/{gid}", status_code=204)
def borrar_gasto(gid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, CostoExterno, gid, "Gasto")); db.commit()
