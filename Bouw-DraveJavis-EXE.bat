@echo off
title DraveJavis - EXE bouwen
cd /d "%~dp0"
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" ( echo Eerst Installeer-DraveJavis.bat draaien. & pause & exit /b 1 )
"%VPY%" -m pip install pyinstaller >nul
"%VPY%" -m PyInstaller --noconfirm --clean --windowed --onedir --name DraveJavis --icon assets\icon.ico --add-data "assets;assets" --collect-all faster_whisper --collect-all ctranslate2 --collect-all neuvoice --collect-all onnxruntime --collect-all sounddevice --collect-data av --hidden-import brein --hidden-import stem --hidden-import oren --hidden-import geheugen --hidden-import vaardigheden --hidden-import zoeken --hidden-import pc --collect-all ddgs --collect-all primp --collect-all lxml --exclude-module tkinter --exclude-module PyQt6.QtWebEngineCore --exclude-module PyQt6.QtWebEngineWidgets --exclude-module PyQt6.QtQml --exclude-module PyQt6.QtQuick --exclude-module PyQt6.QtPdf --exclude-module matplotlib --exclude-module PIL javis.py
if errorlevel 1 goto mislukt
if not exist "dist\DraveJavis\DraveJavis.exe" goto mislukt
echo.
echo KLAAR: dist\DraveJavis\DraveJavis.exe
pause
exit /b 0
:mislukt
echo MISLUKT - kijk hierboven voor de fout.
pause
exit /b 1
