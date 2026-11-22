@echo off
title AVIX - Build Simple

echo Installation dependances...
pip install -r requirements.txt pyinstaller

echo.
echo Compilation avec icone AVIX...
pyinstaller --noconfirm --onefile --windowed --name "AVIX Drink System" --icon avix.ico --add-data "avix.ico;." --add-data "logo.png;." --add-data "fonts;fonts" --collect-data customtkinter --hidden-import pystray._win32 avix_drink.py

echo.
echo Termine ! Fichier dans le dossier dist\
pause
