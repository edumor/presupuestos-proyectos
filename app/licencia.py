# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Licencia de uso registrada.

El programa funciona completo con o sin licencia; sin una licencia válida muestra
"Versión sin registrar" en el pie y en los documentos internos. La clave es un texto
`datos.firma` (base64url): los datos son un JSON con titular, CUIT, número, emisión y
vencimiento opcional, firmados con Ed25519. Se valida sin internet con la clave pública
de abajo; las claves se generan con scripts/generar_licencia.py y la clave privada del autor.
"""
from __future__ import annotations

import base64
import json
from datetime import date

from . import ed25519

CLAVE_PUBLICA = bytes.fromhex("b952b4d76b13e0158b2f85c63b430ba82e9db952276875a089833e81a072d194")
PREFIJO = "PRES1-"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def emitir(clave_privada: bytes, titular: str, cuit: str | None = None, numero: str | None = None,
           vence: date | None = None, emitida: date | None = None) -> str:
    datos = {"t": titular.strip(), "c": (cuit or "").strip() or None, "n": numero, "e": str(emitida or date.today()),
             "v": str(vence) if vence else None}
    crudo = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()
    return PREFIJO + _b64(crudo) + "." + _b64(ed25519.firmar(clave_privada, crudo))


def validar(clave: str | None, hoy: date | None = None, publica: bytes = CLAVE_PUBLICA) -> dict:
    """Estado de una clave: sin_licencia, invalida, vencida o registrada."""
    if not clave or not clave.strip():
        return dict(estado="sin_licencia", leyenda="Versión sin registrar")
    texto = "".join(clave.split())
    try:
        if not texto.startswith(PREFIJO):
            raise ValueError
        datos_b64, firma_b64 = texto[len(PREFIJO):].split(".")
        crudo, firma = _unb64(datos_b64), _unb64(firma_b64)
        if not ed25519.verificar(publica, crudo, firma):
            raise ValueError
        d = json.loads(crudo)
    except Exception:
        return dict(estado="invalida", leyenda="Versión sin registrar",
                    mensaje="La clave no es válida. Copiala completa, tal como la recibiste.")
    vence = date.fromisoformat(d["v"]) if d.get("v") else None
    info = dict(titular=d.get("t"), cuit=d.get("c"), numero=d.get("n"), emitida=d.get("e"), vence=vence)
    if vence and vence < (hoy or date.today()):
        return dict(estado="vencida", leyenda="Licencia vencida", **info,
                    mensaje=f"La licencia venció el {vence:%d/%m/%Y}. El programa sigue funcionando.")
    return dict(estado="registrada", leyenda=f"Licenciado a {d.get('t')}", **info)


def leyenda_interna(db) -> str:
    """Texto para los documentos internos: "Licenciado a …" o "Versión sin registrar"."""
    from . import costeo
    return validar(costeo.config(db).licencia)["leyenda"]
