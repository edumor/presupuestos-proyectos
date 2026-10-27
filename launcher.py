# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Punto de entrada del ejecutable (PresupuestosApp.exe).

- Si la aplicación ya está abierta, solo abre el navegador en ella (instancia única).
- Hace un respaldo de la base al iniciar (guarda los últimos 30).
- Usa el puerto 8765 si está libre (así los marcadores del navegador siguen sirviendo).
- La primera vez carga los datos de ejemplo (si PRESUPUESTOS_EJEMPLO_INICIAL=1, que el .exe activa).
"""
import json
import logging
import os
import sqlite3
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime

PUERTO_PREFERIDO = 8765
MAX_BACKUPS = 30


def _data_dir():
    from app.config import data_dir
    return data_dir()


def _archivo_puerto():
    return _data_dir() / "puerto.json"


def _ya_abierta() -> str | None:
    try:
        url = json.loads(_archivo_puerto().read_text())["url"]
        with urllib.request.urlopen(url + "api/health", timeout=1.5) as r:
            if r.status == 200:
                return url
    except Exception:
        pass
    return None


def _puerto_libre() -> int:
    for puerto in (PUERTO_PREFERIDO, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", puerto))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("No hay puertos libres")


def _respaldar() -> None:
    base = _data_dir() / "presupuestos.db"
    if not base.exists():
        return
    destino = _data_dir() / "backups" / f"presupuestos_{datetime.now():%Y%m%d_%H%M%S}.db"
    # backup de SQLite: incluye lo que haya quedado en el archivo -wal si se cerró de golpe
    origen, copia = sqlite3.connect(base), sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    origen.close(); copia.close()
    for viejo in sorted((_data_dir() / "backups").glob("presupuestos_*.db"))[:-MAX_BACKUPS]:
        viejo.unlink()


def _abrir_cuando_responda(url: str) -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(url + "api/health", timeout=1):
                break
        except Exception:
            time.sleep(0.5)
    webbrowser.open(url)


def main() -> None:
    if getattr(sys, "frozen", False):
        os.environ.setdefault("PRESUPUESTOS_EJEMPLO_INICIAL", "1")
    url = _ya_abierta()
    if url:
        webbrowser.open(url)
        return

    logs = _data_dir() / "logs"
    logs.mkdir(exist_ok=True)
    logging.basicConfig(filename=logs / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    _respaldar()
    port = _puerto_libre()
    url = f"http://127.0.0.1:{port}/"
    _archivo_puerto().write_text(json.dumps({"url": url, "pid": os.getpid()}))

    from app import __version__
    sys.stdout.reconfigure(line_buffering=True)
    print("=" * 64)
    print(f"  Presupuestos v{__version__} está funcionando.")
    print(f"  Se abre en el navegador: {url}")
    print()
    print("  NO CIERRES ESTA VENTANA mientras uses el programa.")
    print("  Para salir, cerrala (o presioná Ctrl+C).")
    print(f"  Tus datos están en: {_data_dir()}")
    print("=" * 64)
    threading.Thread(target=_abrir_cuando_responda, args=(url,), daemon=True).start()

    import uvicorn
    from app.main import app
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except Exception:
        logging.exception("Error al ejecutar la aplicación")
        print("\nOcurrió un error. El detalle quedó en:", logs / "app.log")
        input("Presioná Enter para cerrar...")
    finally:
        try:
            _archivo_puerto().unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
