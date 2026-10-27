# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Licencia, aviso de versión nueva y respaldos de la base."""
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import actualizaciones, costeo, importar, licencia, respaldos, seguimiento
from ..database import SessionLocal, get_db
from ..migrar import migrar, revisiones

router = APIRouter(prefix="/api", tags=["Sistema"])
MAX_RESPALDO = 500 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class LicenciaIn(BaseModel):
    clave: str


@router.get("/licencia")
def ver_licencia(db: Session = Depends(get_db)):
    return licencia.validar(costeo.config(db).licencia)


@router.put("/licencia")
def activar_licencia(d: LicenciaIn, db: Session = Depends(get_db)):
    r = licencia.validar(d.clave)
    if r["estado"] == "invalida":
        raise HTTPException(422, r["mensaje"])
    cfg = costeo.config(db)
    cfg.licencia = "".join(d.clave.split())
    db.commit()
    return r


@router.delete("/licencia", status_code=204)
def quitar_licencia(db: Session = Depends(get_db)):
    costeo.config(db).licencia = None
    db.commit()


@router.get("/actualizacion")
def actualizacion(forzar: bool = False, db: Session = Depends(get_db)):
    if not costeo.config(db).buscar_actualizaciones and not forzar:
        return dict(ok=False, desactivado=True, actual=actualizaciones.__version__, hay_nueva=False)
    return actualizaciones.consultar(forzar)


@router.get("/respaldos")
def listar_respaldos():
    return respaldos.listar()


@router.get("/respaldos/descargar")
def descargar_respaldo():
    with tempfile.TemporaryDirectory() as tmp:
        contenido = respaldos.copiar(Path(tmp) / "copia.db").read_bytes()
    nombre = f"Presupuestos_respaldo_{datetime.now():%Y%m%d_%H%M}.db"
    return Response(contenido, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


def _restaurar_desde(ruta: Path) -> dict:
    try:
        rev = respaldos.validar(ruta, revisiones())
    except respaldos.RespaldoInvalido as e:
        raise HTTPException(422, str(e)) from None
    previa = respaldos.restaurar(ruta)
    migrar()  # un respaldo de una versión anterior se actualiza al esquema actual
    with SessionLocal() as db:
        seguimiento.asegurar_plantilla(db)
    return dict(ok=True, version_esquema=rev, copia_previa=previa.name)


@router.post("/respaldos/restaurar")
async def restaurar_archivo(request: Request):
    """Restaura la base desde un archivo .db enviado en el cuerpo (application/octet-stream)."""
    cuerpo = await request.body()
    if not cuerpo:
        raise HTTPException(422, "No se recibió ningún archivo.")
    if len(cuerpo) > MAX_RESPALDO:
        raise HTTPException(413, "El archivo es demasiado grande.")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "subido.db"
        ruta.write_bytes(cuerpo)
        return _restaurar_desde(ruta)


@router.post("/respaldos/{nombre}/restaurar")
def restaurar_automatico(nombre: str):
    ruta = respaldos.carpeta() / Path(nombre).name
    if not ruta.exists() or ruta.suffix != ".db":
        raise HTTPException(404, "Respaldo inexistente")
    with tempfile.TemporaryDirectory() as tmp:  # se restaura una copia: el original queda intacto
        copia = Path(tmp) / "copia.db"
        copia.write_bytes(ruta.read_bytes())
        return _restaurar_desde(copia)




# --- Importación desde Excel ---
MAX_EXCEL = 20 * 1024 * 1024


@router.get("/importar/plantilla")
def plantilla_importacion(db: Session = Depends(get_db)):
    return Response(importar.plantilla(db), media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="Presupuestos_planilla_importacion.xlsx"'})


async def _excel(request: Request) -> bytes:
    cuerpo = await request.body()
    if not cuerpo:
        raise HTTPException(422, "No se recibió ningún archivo.")
    if len(cuerpo) > MAX_EXCEL:
        raise HTTPException(413, "El archivo es demasiado grande.")
    return cuerpo


@router.post("/importar/vista-previa")
async def vista_previa(request: Request, db: Session = Depends(get_db)):
    return importar.procesar(db, await _excel(request), aplicar=False)


@router.post("/importar")
async def importar_excel(request: Request, db: Session = Depends(get_db)):
    r = importar.procesar(db, await _excel(request), aplicar=True)
    if r["errores"]:
        raise HTTPException(422, f"Hay {r['errores']} errores: corregilos en la planilla y volvé a intentar.")
    return r
