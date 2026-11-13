# -*- coding: utf-8 -*-
"""Start the Schematic Linter GUI from an IDE (Spyder, VS Code, PyCharm, IDLE...).

Open this file in Spyder and press F5. The linter window opens; the Spyder
console is busy until you close it again.

No ``pip install -e .`` is needed: this script puts the ``schematic_linter``
package next to it on ``sys.path`` itself. Only the third-party dependencies
must be installed in the Python environment the IDE uses. If one is
missing, the script tells you exactly what to install.

Everything (project folder, checks, thresholds) is set up in the window and
remembered between runs. For scripted use without a window, see
``schematic_linter.cli.run_analysis``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

REQUIRED_PACKAGES = {
    # import name: pip package name
    "networkx": "networkx",
    "fitz": "PyMuPDF",
    "jinja2": "Jinja2",
    "click": "click",
    "rich": "rich",
}


def _missing_packages():
    return [pip for mod, pip in REQUIRED_PACKAGES.items() if importlib.util.find_spec(mod) is None]


def main() -> None:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))

    if importlib.util.find_spec("tkinter") is None:
        print("This Python has no tkinter (GUI toolkit). The standard Windows/Anaconda Python includes it;")
        print("on Linux install your distribution's python3-tk package.")
        return

    missing = _missing_packages()
    if missing:
        print("Missing Python packages: " + ", ".join(missing))
        print("Install them into the environment this IDE uses, e.g. in the Spyder console:")
        print("    %pip install " + " ".join(missing))
        print("Then restart the console (Consoles > Restart kernel) and run this file again.")
        return

    from schematic_linter.gui import main as gui_main

    gui_main([])


if __name__ == "__main__":
    main()
