"""PyInstaller entry point for the windowed GUI build (SchematicLinter.exe).

Like ``entry_point.py``, this exists because PyInstaller needs a real
script to analyze rather than a ``module:function`` entry point string.
"""

from schematic_linter.gui import main

if __name__ == "__main__":
    main()
