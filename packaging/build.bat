@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Generar instalador de Presupuestos
cd /d "%~dp0.."

echo.
echo === Generar el instalador de Presupuestos ===
echo.

rem ---------- 1. Python ----------
echo [1/6] Buscando Python 3.12...
set "PY="
py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY python --version 2>nul | findstr /r "3\.1[2-9]" >nul && set "PY=python"
if not defined PY (
  echo    No encontre Python 3.12 o superior.
  echo    Instalalo desde https://www.python.org/downloads/ tildando "Add python.exe to PATH"
  echo    y volve a ejecutar este archivo.
  goto :error
)
%PY% --version

rem ---------- 2. Entorno ----------
echo [2/6] Preparando entorno de compilacion (.venv-build)...
if not exist .venv-build ( %PY% -m venv .venv-build || goto :error )
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip --quiet || goto :error
pip install --quiet -r requirements-build.txt pytest httpx || goto :error

rem ---------- 3. Tests ----------
echo [3/6] Ejecutando tests...
python -m pytest -q -p no:cacheprovider || (echo    Hay tests fallando: no se genera el instalador. & goto :error)

for /f "delims=" %%v in ('python -c "import app; print(app.__version__)"') do set "VERSION=%%v"
echo    Version: %VERSION%

rem ---------- 4. Ejecutable ----------
echo [4/6] Empaquetando con PyInstaller (puede tardar unos minutos)...
if exist dist\PresupuestosApp rmdir /s /q dist\PresupuestosApp
pyinstaller --noconfirm --clean --distpath dist --workpath build packaging\presupuestos.spec || goto :error

rem ---------- 5. Inno Setup ----------
echo [5/6] Buscando Inno Setup 6...
call :buscar_iscc
if not defined ISCC (
  echo    Inno Setup no esta instalado. Intento instalarlo con winget...
  winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
  call :buscar_iscc
)
if not defined ISCC (
  echo    No pude instalar Inno Setup automaticamente.
  echo    Descargalo de https://jrsoftware.org/isdl.php, instalalo y volve a ejecutar este archivo.
  goto :error
)

rem ---------- 6. Instalador ----------
echo [6/6] Generando el instalador...
"%ISCC%" /Q /DAppVersion=%VERSION% packaging\installer.iss || goto :error

rem ---------- Carpeta para distribuir ----------
echo Armando la carpeta "Para distribuir"...
if exist "Para distribuir" rmdir /s /q "Para distribuir"
mkdir "Para distribuir"
copy /y "packaging\Output\Presupuestos-Setup-%VERSION%.exe" "Para distribuir\" >nul || goto :error
copy /y "docs\Manual_Presupuestos.pdf" "Para distribuir\Manual de uso - Presupuestos.pdf" >nul
python packaging\leeme.py "%VERSION%" "Para distribuir\LEEME - Primeros pasos.txt" || goto :error

echo.
echo ===========================================================
echo  Listo. La carpeta "Para distribuir" tiene todo lo que hay que enviar:
echo    - Presupuestos-Setup-%VERSION%.exe
echo    - Manual de uso - Presupuestos.pdf
echo    - LEEME - Primeros pasos.txt
echo  Subila completa a Google Drive o adjunta el instalador al Release de GitHub.
echo ===========================================================
explorer "Para distribuir"
pause
exit /b 0

:buscar_iscc
set "ISCC="
for %%p in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%p set "ISCC=%%~p"
)
exit /b 0

:error
echo.
echo *** No se pudo generar el instalador. Revisa los mensajes de arriba. ***
pause
exit /b 1
