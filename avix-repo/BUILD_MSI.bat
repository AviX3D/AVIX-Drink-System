@echo off
title AVIX Drink System - Build MSI

echo.
echo  ================================================
echo   AVIX_3D - Drink System - Build MSI Installer
echo  ================================================
echo.

python --version >nul 2>&1
if not %errorlevel% == 0 (
    echo  [ERREUR] Python non installe.
    echo  https://python.org - coche "Add Python to PATH"
    pause & exit /b 1
)

echo  [1/3] Installation dependances...
pip install customtkinter pyserial pygame pyinstaller keyboard pystray pillow --quiet
echo  [OK]
echo.

echo  [2/3] Compilation .exe avec icone AVIX...
pyinstaller --onefile --windowed --name "AVIX Drink System" ^
    --icon avix.ico ^
    --add-data "avix.ico;." ^
    --hidden-import customtkinter ^
    --hidden-import serial ^
    --hidden-import pygame ^
    --hidden-import keyboard ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    avix_drink.py
if not %errorlevel% == 0 (
    echo  [ERREUR] PyInstaller a echoue.
    pause & exit /b 1
)
echo  [OK]
echo.

echo  [3/3] Creation installeur...
where makensis >nul 2>&1
if not %errorlevel% == 0 (
    echo  NSIS non detecte.
    echo  Installe NSIS : https://nsis.sourceforge.io
    echo  puis relance ce script.
    echo.
    echo  Ton .exe est deja pret dans : dist\AVIX Drink System.exe
    pause & exit /b 0
)
makensis avix_installer.nsi
echo  [OK]

echo.
echo  ================================================
echo   BUILD TERMINE !
echo   Installeur : AVIX_Drink_System_Setup.exe
echo  ================================================
pause
