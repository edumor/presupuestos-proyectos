# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Consultas HTTPS de solo lectura (BCRA y GitHub) que funcionen en cualquier PC con Windows.

1. Primero con Python (urllib), con verificación de certificados.
2. Si falla en Windows, se repite con PowerShell (Invoke-WebRequest), que usa el mismo sistema de
   red que el navegador: completa solo las cadenas de certificados incompletas (le pasa a algunos
   servidores públicos, como el del BCRA) y usa el proxy de la empresa con las credenciales de
   Windows. Nunca se desactiva la verificación de certificados.
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

PS = (
    "$ErrorActionPreference='Stop';"
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;"
    "$px=[Net.WebRequest]::DefaultWebProxy; if($px){$px.Credentials=[Net.CredentialCache]::DefaultCredentials};"
    "$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 25 -Uri $env:PRES_URL;"
    "$b=$r.RawContentStream.ToArray();"
    "[Console]::Out.Write([Convert]::ToBase64String($b))"
)


def es_windows() -> bool:
    return sys.platform == "win32"


class ErrorRed(Exception):
    pass


class ErrorHTTP(ErrorRed):
    def __init__(self, status: int, cuerpo: bytes):
        super().__init__(f"HTTP {status}")
        self.status, self.cuerpo = status, cuerpo


def _motivo(e: Exception) -> str:
    r = getattr(e, "reason", e)
    if isinstance(r, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(r):
        return "no se pudo verificar el certificado del sitio"
    if isinstance(r, TimeoutError) or "timed out" in str(r):
        return "el sitio no respondió a tiempo"
    if "getaddrinfo" in str(r) or "Name or service not known" in str(r):
        return "no se encontró el sitio (¿hay internet?)"
    if "407" in str(r) or "Proxy" in str(r):
        return "el proxy de la red pidió autenticación"
    return str(r)[:160]


def _con_python(url: str, accept: str, agente: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": agente})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise ErrorHTTP(e.code, e.read()) from e


def _con_powershell(url: str, accept: str) -> bytes:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = {**os.environ, "PRES_URL": url, "PRES_ACCEPT": accept}
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", PS],
                       capture_output=True, timeout=40, env=env, creationflags=flags)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "ignore")
        for codigo in (400, 401, 403, 404, 429, 500, 502, 503):
            if f"({codigo})" in err:
                raise ErrorHTTP(codigo, b"")
        raise ErrorRed(err.strip().splitlines()[0][:200] if err.strip() else "PowerShell no pudo hacer la consulta")
    import base64
    return base64.b64decode(r.stdout.strip())


def obtener(url: str, accept: str = "application/json", agente: str = "Presupuestos", timeout: float = 20) -> bytes:
    try:
        return _con_python(url, accept, agente, timeout)
    except ErrorHTTP:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as e:
        motivo = _motivo(e)
        if not es_windows():
            raise ErrorRed(motivo) from e
    try:  # segundo intento con el sistema de red de Windows
        return _con_powershell(url, accept)
    except ErrorHTTP:
        raise
    except Exception as e2:
        raise ErrorRed(f"{motivo}; con Windows: {_motivo(e2)}") from e2


def obtener_json(url: str, **kw) -> dict:
    datos = obtener(url, **kw)
    try:
        return json.loads(datos.decode("utf-8-sig"))
    except ValueError as e:
        raise ErrorRed("la respuesta no es JSON (¿un proxy o portal de la red interceptó la consulta?)") from e
