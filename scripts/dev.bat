@echo off
REM Prepara el entorno de desarrollo y arranca la aplicacion.
cd /d "%~dp0.."
if not exist .venv (
  py -3.12 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements-dev.txt
python launcher.py
