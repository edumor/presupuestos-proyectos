# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Ubicación de datos y parámetros de arranque.

En Windows los datos viven en %LOCALAPPDATA%\\PresupuestosApp, fuera de la
carpeta del programa, para que una reinstalación no borre la base.
Se puede forzar otra carpeta con la variable PRESUPUESTOS_DATA_DIR.
"""
import os
import sys
from pathlib import Path

APP_NAME = "PresupuestosApp"


def data_dir() -> Path:
    override = os.environ.get("PRESUPUESTOS_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    else:
        base = Path.home() / f".{APP_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    (base / "backups").mkdir(exist_ok=True)
    return base


def db_url() -> str:
    return f"sqlite:///{data_dir() / 'presupuestos.db'}"


def resource_root() -> Path:
    """Raíz de los recursos: el proyecto en desarrollo, sys._MEIPASS dentro del ejecutable."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def frontend_dir() -> Path:
    return resource_root() / "frontend"


def logo_personalizado() -> Path:
    return data_dir() / "logo.png"


def logo_efectivo() -> Path | None:
    """Logo de la empresa cargado en Configuración (opcional)."""
    p = logo_personalizado()
    return p if p.exists() else None
