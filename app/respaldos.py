# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Copia y restauración de la base de datos (SQLite)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .config import data_dir

MAX_ANTES = 10


class RespaldoInvalido(Exception):
    pass


def archivo_base() -> Path:
    return data_dir() / "presupuestos.db"


def carpeta() -> Path:
    return data_dir() / "backups"


def copiar(destino: Path) -> Path:
    """Copia consistente de la base (API de backup de SQLite: incluye lo pendiente en el WAL)."""
    origen, copia = sqlite3.connect(archivo_base()), sqlite3.connect(destino)
    try:
        with copia:
            origen.backup(copia)
    finally:
        origen.close(); copia.close()
    return destino


def listar() -> list[dict]:
    out = []
    archivos = [*carpeta().glob("presupuestos_*.db"), *carpeta().glob("previa_restauracion_*.db")]
    for f in sorted(archivos, key=lambda f: f.stat().st_mtime, reverse=True):
        st = f.stat()
        out.append(dict(nombre=f.name, tamano=st.st_size,
                        fecha=datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                        antes_de_restaurar=f.name.startswith("previa_")))
    return out


def validar(ruta: Path, revisiones: list[str]) -> str:
    """Comprueba que el archivo sea una base de este programa y devuelve su versión de esquema."""
    try:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RespaldoInvalido("El archivo está dañado.")
            tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"configuracion", "proyectos", "personas", "alembic_version"} <= tablas:
                raise RespaldoInvalido("El archivo no es un respaldo de este programa.")
            rev = con.execute("SELECT version_num FROM alembic_version").fetchone()
        finally:
            con.close()
    except sqlite3.DatabaseError:
        raise RespaldoInvalido("El archivo no es una base de datos válida.") from None
    if not rev or rev[0] not in revisiones:
        raise RespaldoInvalido("El respaldo es de una versión más nueva del programa: actualizá el programa primero.")
    return rev[0]


def restaurar(ruta: Path) -> Path:
    """Guarda una copia de la base actual y la reemplaza por `ruta`. Devuelve la copia previa."""
    from .database import engine
    previa = copiar(carpeta() / f"previa_restauracion_{datetime.now():%Y%m%d_%H%M%S}.db")
    for vieja in sorted(carpeta().glob("previa_restauracion_*.db"))[:-MAX_ANTES]:
        vieja.unlink()
    engine.dispose()
    origen, destino = sqlite3.connect(ruta), sqlite3.connect(archivo_base())
    try:
        with destino:
            origen.backup(destino)
    finally:
        origen.close(); destino.close()
    engine.dispose()
    return previa
