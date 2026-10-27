# -*- mode: python ; coding: utf-8 -*-
# Empaquetado con PyInstaller (modo carpeta). Se ejecuta desde packaging\build.bat.
import os
from PyInstaller.utils.hooks import collect_submodules

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [
    (os.path.join(RAIZ, "frontend"), "frontend"),
    (os.path.join(RAIZ, "migrations"), "migrations"),
    (os.path.join(RAIZ, "alembic.ini"), "."),
]
manual = os.path.join(RAIZ, "docs", "Manual_Presupuestos.pdf")
if os.path.exists(manual):
    datas.append((manual, "docs"))

# Los paquetes .testing de alembic/sqlalchemy son herramientas de sus propios tests: no se incluyen
# (además, importarlos falla según la combinación de versiones).
sin_tests = lambda nombre: ".testing" not in nombre  # noqa: E731
hidden = (collect_submodules("app") + collect_submodules("uvicorn", filter=sin_tests)
          + collect_submodules("alembic", filter=sin_tests)
          + ["sqlalchemy.dialects.sqlite", "openpyxl", "reportlab", "PIL"])

a = Analysis(
    [os.path.join(RAIZ, "launcher.py")],
    pathex=[RAIZ],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "IPython", "matplotlib", "numpy", "pandas",
              "alembic.testing", "sqlalchemy.testing"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="PresupuestosApp",
    console=True,  # la ventana muestra el estado; al cerrarla se detiene el programa
    icon=os.path.join(SPECPATH, "recursos", "icono.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="PresupuestosApp")
