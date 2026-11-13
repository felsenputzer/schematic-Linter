<#
.SYNOPSIS
    Builds standalone SchematicLinter.exe (GUI) and schematic-linter.exe (CLI) for Windows using PyInstaller.

.DESCRIPTION
    Installs the project (and PyInstaller) into whatever Python environment
    is currently active, then runs PyInstaller against schematic-linter.spec.
    Run this on a Windows machine with Python 3.10+ on PATH.

.EXAMPLE
    cd packaging\windows
    .\build.ps1
#>

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$LinterRoot = Resolve-Path (Join-Path $ScriptDir "..\..")

Push-Location $LinterRoot
try {
    Write-Host "Installing schematic-linter and build dependencies..."
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python -m pip install pyinstaller

    Write-Host "Running PyInstaller..."
    pyinstaller --noconfirm --clean `
        --distpath (Join-Path $ScriptDir "dist") `
        --workpath (Join-Path $ScriptDir "build") `
        (Join-Path $ScriptDir "schematic-linter.spec")
}
finally {
    Pop-Location
}

$DistDir = Join-Path $ScriptDir "dist"
Write-Host "Build complete:"
Write-Host "  GUI (give this to users): $(Join-Path $DistDir 'SchematicLinter.exe')"
Write-Host "  Command line:             $(Join-Path $DistDir 'schematic-linter.exe')"
