@echo off
rem Genera una clave de licencia firmada (uso del autor). Necesita licencias_privado\clave_privada.txt
chcp 65001 >nul
pushd "%~dp0.."
if exist .venv\Scripts\python.exe (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
"%PY%" scripts\generar_licencia.py %*
popd
pause
