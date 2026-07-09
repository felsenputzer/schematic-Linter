# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a standalone Windows build of schematic-linter.

Build on a Windows machine from this folder with:

    pyinstaller schematic-linter.spec

(or just run ``build.ps1``, which does this plus the pip install step).
Produces ``dist\\schematic-linter.exe`` -- a single self-contained file that
needs no separate Python install on the target machine.
"""

import pathlib

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = pathlib.Path(SPECPATH)
LINTER_ROOT = SPEC_DIR.parent.parent
TEMPLATES_DIR = LINTER_ROOT / "schematic_linter" / "report" / "templates"

# Rules and pattern recognizers are auto-discovered at runtime via
# pkgutil.iter_modules() rather than imported by name anywhere in the source,
# so PyInstaller's static import scan can't find them on its own -- they have
# to be listed explicitly or they'll silently be missing from the build.
hidden_imports = collect_submodules("schematic_linter.rules") + collect_submodules(
    "schematic_linter.patterns"
)

a = Analysis(
    [str(SPEC_DIR / "entry_point.py")],
    pathex=[str(LINTER_ROOT)],
    binaries=[],
    datas=[(str(TEMPLATES_DIR), "schematic_linter/report/templates")],
    hiddenimports=hidden_imports,
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
    a.binaries,
    a.datas,
    [],
    name="schematic-linter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
