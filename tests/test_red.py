# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Segundo intento con PowerShell cuando Python no puede verificar el certificado (simulado)."""
import base64
import ssl
import subprocess
import urllib.error

import pytest

from app import bcra, red


def _falla_certificado(*a, **k):
    raise urllib.error.URLError(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate"))


def test_reintento_con_windows(monkeypatch):
    monkeypatch.setattr(red, "es_windows", lambda: True)
    monkeypatch.setattr(red.urllib.request, "urlopen", _falla_certificado)
    llamadas = []

    def ps(args, **kw):
        llamadas.append(kw["env"]["PRES_URL"])
        cuerpo = b'{"results": {"fecha": "2026-10-27", "detalle": [{"codigoMoneda": "USD", "tipoCotizacion": 1455.5}]}}'
        return subprocess.CompletedProcess(args, 0, base64.b64encode(cuerpo), b"")
    monkeypatch.setattr(red.subprocess, "run", ps)
    fecha, valores = bcra.cotizaciones()
    assert valores["USD"] == 1455.5 and llamadas[0].startswith("https://api.bcra.gob.ar/")


def test_mensaje_claro_si_fallan_los_dos(monkeypatch):
    monkeypatch.setattr(red, "es_windows", lambda: True)
    monkeypatch.setattr(red.urllib.request, "urlopen", _falla_certificado)
    monkeypatch.setattr(red.subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(
        args, 1, b"", b"Invoke-WebRequest : No es posible conectar con el servidor remoto\r\n"))
    with pytest.raises(bcra.ErrorBCRA) as e:
        bcra.cotizaciones()
    assert "certificado" in str(e.value) and "No es posible conectar" in str(e.value)


def test_sin_windows_no_usa_powershell(monkeypatch):
    monkeypatch.setattr(red, "es_windows", lambda: False)
    monkeypatch.setattr(red.urllib.request, "urlopen", _falla_certificado)
    monkeypatch.setattr(red.subprocess, "run", lambda *a, **k: pytest.fail("no debería llamar a PowerShell"))
    with pytest.raises(red.ErrorRed, match="certificado"):
        red.obtener("https://api.bcra.gob.ar/x")
