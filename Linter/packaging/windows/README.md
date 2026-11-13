# Standalone Windows build

Packages the linter with [PyInstaller](https://pyinstaller.org/) into two
single-file executables that run on a Windows machine with no Python
installed:

| File | What it is |
|---|---|
| `SchematicLinter.exe` | The graphical tool. **This is the one to give to users**: double-click, choose the project folder, click *Run checks*. |
| `schematic-linter.exe` | The command-line tool, for scripting/CI (`schematic-linter.exe analyze C:\path\to\ProjectFolder`). |

PyInstaller doesn't cross-compile, so this **must be built on a Windows
machine** (or a Windows CI runner -- see
[`.github/workflows/windows.yml`](../../../.github/workflows/windows.yml),
which builds and smoke-tests both executables on every push and uploads
them as the `schematic-linter-windows` artifact).

## Build

On Windows, with Python 3.10+ on `PATH`:

```powershell
cd packaging\windows
.\build.ps1
```

This installs the project (editable) plus `pyinstaller` into whatever Python
environment is currently active, then runs PyInstaller against
`schematic-linter.spec`. The results are written to
`packaging\windows\dist\`.

## Deploying to users

Copy `SchematicLinter.exe` anywhere (a network share works, so does the
desktop) -- it's fully self-contained (Python interpreter, all
dependencies, the report template). Each user's settings are stored in
`%APPDATA%\SchematicLinter\settings.json`. To give everyone the same
checks/thresholds, save a profile from the GUI (*File → Save check
profile...*) and share that `.json` file.

Things to expect:

- **Start-up takes a few seconds**: a single-file exe unpacks itself to a
  temp folder on every launch.
- **SmartScreen / antivirus**: an unsigned exe downloaded from the internet
  triggers "Windows protected your PC" (*More info → Run anyway*), and some
  antivirus products are wary of PyInstaller executables in general. For a
  wider rollout, sign the exe with your organization's code-signing
  certificate (`signtool sign ...`), or ask IT to allow-list it.
- You can also drop a project folder onto `SchematicLinter.exe`: it opens
  with that folder pre-selected.

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
- The spec excludes `numpy`, `onnxruntime` and PyMuPDF's ONNX layout models.
  Recent PyMuPDF versions pull these in for an optional AI layout feature the
  linter doesn't use. This cuts each executable from roughly 110 MB to
  roughly 50 MB (measured on a Linux test build).
- `SchematicLinter.exe --smoke-test <project> <output>` opens the real
  window, runs one analysis without user interaction and exits with the
  same code as the CLI (CI uses this).
- `build\` and `dist\` (PyInstaller's working and output directories) are
  git-ignored; rebuild locally rather than expecting a checked-in `.exe`.
