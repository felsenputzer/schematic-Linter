# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a standalone Windows build of schematic-linter.

Build on a Windows machine from this folder with:

    pyinstaller schematic-linter.spec

(or just run ``build.ps1``, which does this plus the pip install step).
Produces two single-file executables in ``dist\\`` that need no Python
install on the target machine:

- ``SchematicLinter.exe`` -- the windowed GUI (what to hand to users).
- ``schematic-linter.exe`` -- the command-line tool (CI, scripting).
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

# Newer PyMuPDF releases depend on numpy + onnxruntime (and ship ~40 MB of
# ONNX models) for their optional AI layout analysis, which this tool never
# uses. Leaving them out roughly halves the .exe size; the full pipeline is
# verified to run without them. networkx likewise only imports numpy/scipy/
# pandas/matplotlib for features we don't use.
EXCLUDES = [
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "onnxruntime",
    "pymupdf.layout",
    "IPython",
    "pytest",
]

COMMON = dict(
    pathex=[str(LINTER_ROOT)],
    binaries=[],
    datas=[(str(TEMPLATES_DIR), "schematic_linter/report/templates")],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

EXE_OPTIONS = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


def _without_layout_models(toc):
    # The pymupdf hook collects the layout feature's model files as data even
    # though the module itself is excluded above.
    return [entry for entry in toc if not entry[0].replace("\\", "/").startswith("pymupdf/layout/")]


def build_exe(entry_script, name, console):
    analysis = Analysis([str(SPEC_DIR / entry_script)], **COMMON)
    analysis.datas = _without_layout_models(analysis.datas)
    return EXE(
        PYZ(analysis.pure),
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name=name,
        console=console,
        **EXE_OPTIONS,
    )


gui_exe = build_exe("entry_point_gui.py", "SchematicLinter", console=False)
cli_exe = build_exe("entry_point.py", "schematic-linter", console=True)
