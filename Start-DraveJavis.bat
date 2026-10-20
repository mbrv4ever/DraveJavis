@echo off
title DraveJavis
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" javis.py
  exit /b 0
)
echo Eerst installeren: dubbelklik Installeer-DraveJavis.bat
pause
