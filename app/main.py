# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Aplicación FastAPI: API bajo /api e interfaz HTML en /."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from . import __version__, costeo, seguimiento
from . import ejemplo as ejemplo_datos
from .config import data_dir, frontend_dir
from .database import SessionLocal
from .migrar import migrar
from .models import Persona
from .routers import (config, cotizaciones, dashboard, ejemplo, equipo, estructura, exportar, horas, presupuestos,
                      proyectos)


def _primer_inicio(db) -> None:
    """En la primera ejecución del instalado, carga los datos de ejemplo (una sola vez)."""
    marca = data_dir() / ".inicializado"
    if marca.exists():
        return
    if os.environ.get("PRESUPUESTOS_EJEMPLO_INICIAL") == "1" and not db.scalars(select(Persona)).first():
        try:
            ejemplo_datos.cargar(db)
        except ejemplo_datos.BaseNoCompatible:
            pass
    marca.write_text(__version__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrar()
    with SessionLocal() as db:
        costeo.config(db)  # asegura la fila de configuración
        seguimiento.asegurar_plantilla(db)
        _primer_inicio(db)
    yield


app = FastAPI(title="Presupuestos y seguimiento de proyectos", version=__version__, lifespan=lifespan)


@app.exception_handler(costeo.FaltaCotizacion)
async def _falta_cotizacion(_: Request, exc: costeo.FaltaCotizacion):
    return JSONResponse(status_code=422, content={"detail": str(exc), "moneda": exc.moneda})


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok", "version": __version__, "data_dir": str(data_dir())}


for r in (config.router, cotizaciones.router, equipo.router, estructura.router, ejemplo.router,
          proyectos.router, presupuestos.router, horas.router, dashboard.router, exportar.router):
    app.include_router(r)

app.mount("/", StaticFiles(directory=frontend_dir(), html=True), name="frontend")
