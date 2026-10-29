@echo off
title DraveJavis - EXE bouwen
cd /d "%~dp0"
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" ( echo Eerst Installeer-DraveJavis.bat draaien. & pause & exit /b 1 )
"%VPY%" -m pip install pyinstaller >nul
rem Jouw gegevens naast de exe (DraveJavis-data) veilig opzij zetten: PyInstaller wist dist\DraveJavis (29-10-2026)
if exist "_bewaar_data" rmdir /s /q "_bewaar_data"
if exist "dist\DraveJavis\DraveJavis-data" robocopy "dist\DraveJavis\DraveJavis-data" "_data_reserve" /MIR /NFL /NDL /NJH /NJS >nul
if exist "dist\DraveJavis\DraveJavis-data" move "dist\DraveJavis\DraveJavis-data" "_bewaar_data" >nul
if exist "dist\DraveJavis\DraveJavis-data" goto bewaarfout
"%VPY%" -m PyInstaller --noconfirm --clean --windowed --onedir --name DraveJavis --icon assets\icon.ico --add-data "assets;assets" --collect-all faster_whisper --collect-all ctranslate2 --collect-all neuvoice --collect-all onnxruntime --collect-all sounddevice --collect-data av --hidden-import brein --hidden-import drave_motor --hidden-import stem --hidden-import oren --hidden-import geheugen --hidden-import vaardigheden --hidden-import zoeken --hidden-import pc --hidden-import ochtend --hidden-import weer_engine --hidden-import agenda_model --hidden-import sqlite3 --collect-all ddgs --collect-all primp --collect-all lxml --exclude-module tkinter --exclude-module PyQt6.QtWebEngineCore --exclude-module PyQt6.QtWebEngineWidgets --exclude-module PyQt6.QtQml --exclude-module PyQt6.QtQuick --exclude-module PyQt6.QtPdf --exclude-module matplotlib --exclude-module PIL javis.py
set "FOUT=%errorlevel%"
if not exist "dist\DraveJavis" mkdir "dist\DraveJavis"
if exist "_bewaar_data" if exist "dist\DraveJavis\DraveJavis-data" rmdir /s /q "dist\DraveJavis\DraveJavis-data"
if exist "_bewaar_data" move "_bewaar_data" "dist\DraveJavis\DraveJavis-data" >nul
if not "%FOUT%"=="0" goto mislukt
if not exist "dist\DraveJavis\DraveJavis.exe" goto mislukt
if exist "DraveJavis-Snelgids.pdf" copy /y "DraveJavis-Snelgids.pdf" "dist\DraveJavis\" >nul
echo.
echo KLAAR: dist\DraveJavis\DraveJavis.exe
pause
exit /b 0
:bewaarfout
echo FOUT: kon je gegevens niet opzij zetten - bouwen gestopt.
pause
exit /b 1
:mislukt
echo MISLUKT - kijk hierboven voor de fout.
pause
exit /b 1
