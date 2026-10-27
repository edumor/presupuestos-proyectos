# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import select

from .. import costeo, licencia
from ..config import logo_personalizado
from ..database import get_db
from ..models import CostoFijo, Cotizacion, Persona, Proyecto
from ..schemas import MONEDAS, ConfigIn, ConfigOut

router = APIRouter(prefix="/api/config", tags=["Configuración"])
MAX_LOGO = 2 * 1024 * 1024


def logo_path():
    return logo_personalizado()


def hay_datos(db: Session) -> bool:
    """La moneda base solo se puede cambiar antes de cargar importes o cotizaciones."""
    return any(db.scalars(select(m.id).limit(1)).first() is not None
               for m in (Persona, CostoFijo, Proyecto, Cotizacion))


def _out(db: Session, cfg) -> ConfigOut:
    o = ConfigOut.model_validate(cfg)
    o.tiene_logo = logo_path().exists()
    o.puede_cambiar_base = not hay_datos(db)
    o.licencia_info = licencia.validar(cfg.licencia)
    return o


@router.get("", response_model=ConfigOut)
def leer(db: Session = Depends(get_db)):
    return _out(db, costeo.config(db))


@router.put("", response_model=ConfigOut)
def guardar(datos: ConfigIn, db: Session = Depends(get_db)):
    cfg = costeo.config(db)
    valores = datos.model_dump()
    nueva = (valores.pop("moneda_base") or cfg.moneda_base).upper()
    if nueva != cfg.moneda_base:
        if nueva not in MONEDAS:
            raise HTTPException(422, "Moneda base no admitida")
        if hay_datos(db):
            raise HTTPException(409, "La moneda base solo se puede cambiar sin datos cargados: borre primero "
                                     "los datos de ejemplo, el equipo, la estructura, los proyectos y las cotizaciones.")
        cfg.moneda_base = nueva
    for k, v in valores.items():
        if isinstance(v, str):
            v = v.strip() or None
        setattr(cfg, k, v)
    db.commit()
    return _out(db, cfg)


class LogoIn(BaseModel):
    data_url: str  # "data:image/png;base64,..." o "data:image/jpeg;base64,..."


@router.put("/logo", status_code=204)
def subir_logo(d: LogoIn):
    """Guarda el logo de la empresa (PNG o JPG, máx. 2 MB) normalizado a PNG."""
    try:
        cabecera, datos = d.data_url.split(",", 1)
        crudo = base64.b64decode(datos)
    except Exception:
        raise HTTPException(422, "Imagen inválida")
    if len(crudo) > MAX_LOGO:
        raise HTTPException(422, "El logo supera 2 MB")
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(crudo))
        img.load()
    except Exception:
        raise HTTPException(422, "El archivo no es una imagen PNG o JPG válida")
    img = img.convert("RGBA")
    img.thumbnail((800, 300))
    img.save(logo_path(), "PNG")


@router.get("/logo")
def ver_logo():
    """Logo de la empresa (opcional: si no se cargó ninguno, 404)."""
    p = logo_path()
    if not p.exists():
        raise HTTPException(404, "Sin logo")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.delete("/logo", status_code=204)
def borrar_logo():
    logo_path().unlink(missing_ok=True)
