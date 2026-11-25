# -*- mode: python ; coding: utf-8 -*-
"""Windows build for Cursor Auto Run. Run it with build.bat on Windows."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("PySide6")
datas += [("assets", "assets")]

a = Analysis(
    ["cursor_auto_run/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports
    + [
        "uiautomation",
        "comtypes",
        "comtypes.client",
        "comtypes.stream",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CursorAutoRun",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CursorAutoRun",
)
