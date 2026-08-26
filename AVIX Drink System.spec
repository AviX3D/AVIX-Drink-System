# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['avix_drink.py'],
    pathex=[],
    binaries=[],
    datas=[('avix.ico', '.')],
    hiddenimports=['customtkinter', 'serial', 'pygame', 'keyboard', 'pystray', 'PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AVIX Drink System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['avix.ico'],
)
