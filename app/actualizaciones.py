# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Aviso de versión nueva: consulta la última versión publicada en GitHub Releases.

Solo lee datos públicos (no envía ningún dato del usuario) y se puede desactivar en Configuración.
"""
from __future__ import annotations

import time

from . import __version__, red

REPO = "edumor/presupuestos-proyectos"
URL_API = f"https://api.github.com/repos/{REPO}/releases/latest"
URL_RELEASES = f"https://github.com/{REPO}/releases"
CACHE_SEG = 6 * 3600
_cache: dict = {}


def version_tupla(v: str) -> tuple[int, ...]:
    partes = []
    for x in v.strip().lstrip("vV").split("."):
        num = "".join(c for c in x if c.isdigit())
        partes.append(int(num) if num else 0)
    return tuple(partes)


def _get_json(url: str) -> dict:
    return red.obtener_json(url, accept="application/vnd.github+json", agente=f"Presupuestos/{__version__}", timeout=5)


def consultar(forzar: bool = False) -> dict:
    ahora = time.time()
    if not forzar and _cache.get("t", 0) > ahora - CACHE_SEG:
        return _cache["dato"]
    try:
        r = _get_json(URL_API)
        ultima = r.get("tag_name", "").lstrip("vV")
        instalador = next((a["browser_download_url"] for a in r.get("assets", [])
                           if a.get("name", "").lower().endswith(".exe")), None)
        dato = dict(ok=True, actual=__version__, ultima=ultima,
                    hay_nueva=bool(ultima) and version_tupla(ultima) > version_tupla(__version__),
                    nombre=r.get("name"), fecha=(r.get("published_at") or "")[:10],
                    notas=(r.get("body") or "")[:2000], url=r.get("html_url") or URL_RELEASES, instalador=instalador)
    except Exception:
        dato = dict(ok=False, actual=__version__, hay_nueva=False, url=URL_RELEASES,
                    mensaje="No se pudo consultar GitHub (sin internet o servicio no disponible).")
    _cache.update(t=ahora, dato=dato)
    return dato
