@echo off
title DraveJavis - installeren
cd /d "%~dp0"
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( echo Geen Python 3.10 - 3.13 gevonden. Installeer Python van python.org. & pause & exit /b 1 )
echo Python: %PY%
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo Installeren mislukt. & pause & exit /b 1 )
echo.
echo KLAAR. Start DraveJavis met Start-DraveJavis.bat
pause
