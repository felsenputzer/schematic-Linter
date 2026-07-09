"""PyInstaller entry point.

PyInstaller needs an actual script to analyze (not a ``module:function``
string like the ``schematic-linter`` console-script entry point in
``pyproject.toml`` uses), so this tiny wrapper just calls into the real CLI.
"""

from schematic_linter.cli import main

if __name__ == "__main__":
    main()
