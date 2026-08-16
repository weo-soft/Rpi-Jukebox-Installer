# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Phoniebox Installer (Windows onefile build).

Run from the repo root:
    pyinstaller packaging/windows/phoniebox-installer.spec

Produces: dist/Phoniebox-Installer.exe
"""

import os

# SPECPATH is provided by PyInstaller and points to the directory
# containing this spec file (packaging/windows). The repo root is two
# levels above.
project_root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

a = Analysis(
    [os.path.join(project_root, "phoniebox_installer", "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=[
        (
            os.path.join(project_root, "phoniebox_installer", "resources"),
            "phoniebox_installer/resources",
        ),
    ],
    hiddenimports=[
        "paramiko",
        "ruamel.yaml",
        "zeroconf",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Phoniebox-Installer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windows: kein Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
