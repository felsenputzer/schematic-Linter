"""``python -m schematic_linter``: opens the GUI when started without
arguments, otherwise behaves like the ``schematic-linter`` command line."""

import sys


def _run() -> None:
    if len(sys.argv) > 1:
        from .cli import main

        main(prog_name="schematic-linter")
    else:
        from .gui import main

        main([])


if __name__ == "__main__":
    _run()
