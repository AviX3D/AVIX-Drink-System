@echo off
title AVIX Drink System - Build EXE
color 0C

echo.
echo  ================================================
echo   AVIX_3D - Drink System - Build Windows
echo  ================================================
echo.

python --version >nul 2>&1
if not %errorlevel% == 0 (
    echo  [ERREUR] Python n'est pas installe.
    echo  Telecharge-le sur https://python.org
    echo  IMPORTANT : coche "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

python --version
echo  Python detecte - OK
echo.

echo  [1/3] Installation des dependances...
pip install -r requirements.txt pyinstaller
echo  [OK] Dependances installees.
echo.

echo  [2/3] Rebuild serialport...
echo  (ignore pour Python - non necessaire)
echo.

echo  [3/3] Compilation du .exe...
pyinstaller --noconfirm --onefile --windowed --name "AVIX Drink System" --icon avix.ico --add-data "avix.ico;." --add-data "logo.png;." --add-data "fonts;fonts" --collect-data customtkinter --hidden-import pystray._win32 avix_drink.py

if not %errorlevel% == 0 (
    echo.
    echo  [ERREUR] La compilation a echoue.
    echo  Lance BUILD_SIMPLE.bat a la place.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   BUILD TERMINE !
echo   Ton .exe est dans le dossier : dist\
echo   Fichier : AVIX Drink System.exe
echo  ================================================
echo.
pause
