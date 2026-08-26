@echo off
title AVIX - Build Simple

echo Installation dependances...
pip install customtkinter pyserial pygame pyinstaller keyboard pystray pillow

echo.
echo Compilation avec icone AVIX...
pyinstaller --onefile --windowed --name "AVIX Drink System" --icon avix.ico --add-data "avix.ico;." avix_drink.py

echo.
echo Termine ! Fichier dans le dossier dist\
pause
