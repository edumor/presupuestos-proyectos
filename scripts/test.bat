@echo off
REM Ejecuta los tests.
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python -m pytest -q
