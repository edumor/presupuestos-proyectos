# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Genera claves de licencia firmadas (uso del autor).

    python scripts/generar_licencia.py                      # pide los datos
    python scripts/generar_licencia.py --titular "Agencia X S.R.L." --cuit 30-12345678-9 --vence 2027-12-31

La clave privada se lee de licencias_privado/clave_privada.txt (fuera del repositorio: está en
.gitignore) o de la ruta indicada con --clave. NUNCA la publiques ni la envíes a nadie: con ella
cualquiera puede emitir licencias. Cada licencia emitida se guarda en licencias_privado/emitidas/
y se anota en licencias_privado/registro.csv.

    python scripts/generar_licencia.py --nueva-clave        # crea un par de claves nuevo
"""
import argparse
import csv
import os
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app import ed25519, licencia  # noqa: E402

CARPETA = RAIZ / "licencias_privado"


def nueva_clave(ruta: Path) -> None:
    if ruta.exists():
        sys.exit(f"Ya existe {ruta}: no la reemplazo (las licencias emitidas dejarían de valer).")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    secreto = os.urandom(32)
    ruta.write_text(secreto.hex())
    print("Clave privada guardada en", ruta)
    print("Clave pública (copiala en app/licencia.py, CLAVE_PUBLICA):", ed25519.clave_publica(secreto).hex())


def preguntar(texto: str, obligatorio: bool = False) -> str:
    while True:
        v = input(texto).strip()
        if v or not obligatorio:
            return v


def main() -> None:
    a = argparse.ArgumentParser(description="Genera una clave de licencia firmada")
    a.add_argument("--clave", type=Path, default=CARPETA / "clave_privada.txt")
    a.add_argument("--nueva-clave", action="store_true")
    a.add_argument("--titular")
    a.add_argument("--cuit")
    a.add_argument("--numero")
    a.add_argument("--vence", help="AAAA-MM-DD; vacío = sin vencimiento")
    x = a.parse_args()
    if x.nueva_clave:
        return nueva_clave(x.clave)
    if not x.clave.exists():
        sys.exit(f"No encuentro la clave privada en {x.clave}")
    secreto = bytes.fromhex(x.clave.read_text().strip())
    if ed25519.clave_publica(secreto) != licencia.CLAVE_PUBLICA:
        sys.exit("La clave privada no corresponde a la clave pública del programa.")

    registro = CARPETA / "registro.csv"
    previas = list(csv.reader(registro.open(encoding="utf-8"))) if registro.exists() else []
    titular = x.titular or preguntar("Titular (empresa o persona): ", True)
    cuit = x.cuit if x.cuit is not None else preguntar("CUIT (opcional): ")
    numero = x.numero or f"{date.today():%Y}-{len(previas) + 1:04d}"
    vence_txt = x.vence if x.vence is not None else preguntar("Vence (AAAA-MM-DD, vacío = nunca): ")
    vence = date.fromisoformat(vence_txt) if vence_txt else None

    clave = licencia.emitir(secreto, titular, cuit or None, numero, vence)
    assert licencia.validar(clave)["estado"] in ("registrada", "vencida")
    salida = CARPETA / "emitidas"
    salida.mkdir(parents=True, exist_ok=True)
    limpio = re.sub(r"[^\w .-]", "", titular)[:60]
    archivo = salida / f"Licencia {numero} - {limpio}.txt"
    archivo.write_text(
        f"Licencia de Presupuestos y seguimiento de proyectos\n\nTitular: {titular}\n"
        + (f"CUIT: {cuit}\n" if cuit else "") + f"Número: {numero}\n"
        + (f"Vence: {vence:%d/%m/%Y}\n" if vence else "Vence: sin vencimiento\n"), encoding="utf-8")
    with archivo.open("a", encoding="utf-8") as f:
        f.write("\nCómo activarla: en el programa, Configuración → Licencia, pegá esta clave completa y tocá Activar.\n\n"
                f"{clave}\n")
    with registro.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([numero, date.today(), titular, cuit, vence or ""])
    print("\nClave de licencia:\n")
    print(clave)
    print("\nGuardada en", archivo)


if __name__ == "__main__":
    main()
