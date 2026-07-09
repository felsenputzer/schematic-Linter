# Standalone Windows build

Packages `schematic-linter` into a single `schematic-linter.exe` with
[PyInstaller](https://pyinstaller.org/), so it can run on a Windows machine
with no Python installation required.

PyInstaller doesn't cross-compile, so this **must be built on a Windows
machine** (or a Windows CI runner -- see
[`.github/workflows/windows.yml`](../../../.github/workflows/windows.yml),
which builds and smoke-tests this exact spec on every push).

## Build

On Windows, with Python 3.10+ on `PATH`:

```powershell
cd packaging\windows
.\build.ps1
```

This installs the project (editable) plus `pyinstaller` into whatever Python
environment is currently active, then runs PyInstaller against
`schematic-linter.spec`. The result is written to
`packaging\windows\dist\schematic-linter.exe`.

## Use

```powershell
.\dist\schematic-linter.exe analyze C:\path\to\ProjectFolder
```

Same CLI as the regular `schematic-linter` command -- see the main
[README](../../README.md) for usage, input requirements, and what gets
checked. The `.exe` is fully self-contained (it bundles the Python
interpreter, all dependencies, and the HTML report template), so it can be
copied to and run on another Windows machine without installing anything
else.

## Notes

- `schematic-linter.spec` explicitly lists `schematic_linter.rules` and
  `schematic_linter.patterns` as hidden imports. Both packages are
  auto-discovered at runtime via `pkgutil.iter_modules()` rather than
  imported by name anywhere in the source, so PyInstaller's static import
  scan can't find them on its own -- without this, the built `.exe` would
  silently run zero rules.
- The Jinja2 report template
  (`schematic_linter/report/templates/report.html.j2`) is bundled as data
  alongside the code, since PyInstaller doesn't read `setuptools`
  package-data declarations.
- `build\` and `dist\` (PyInstaller's working and output directories) are
  git-ignored; rebuild locally rather than expecting a checked-in `.exe`.
