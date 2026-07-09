<#
.SYNOPSIS
    Builds a standalone schematic-linter.exe for Windows using PyInstaller.

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

$ExePath = Join-Path $ScriptDir "dist\schematic-linter.exe"
Write-Host "Build complete: $ExePath"
