#Requires -Version 5.1
<#
.SYNOPSIS
    Packages MobiTouchRobots as a Windows x64 executable using PyInstaller.

.PARAMETER AppVersion
    Version string embedded in the output filename (default: today's date yyyy.MM.dd).

.EXAMPLE
    .\package-windows-exe-pyinstaller.ps1
    .\package-windows-exe-pyinstaller.ps1 -AppVersion "1.2.0"

.NOTES
    Environment variable overrides:
        APP_NAME               - Application name          (default: MobiTouchRobots)
        BUNDLE_ID              - Bundle / product ID       (default: net.mobitouch.robots)
        SIGN_APP               - Sign the executable       (default: 0)
        SIGN_IDENTITY          - Certificate subject name  (default: "")
        INSTALL_BUILD_DEPS     - pip-install deps          (default: 1)
        FAIL_ON_SIGN_ERROR     - Abort on signing failure  (default: 0)
#>

[CmdletBinding()]
param(
    [string]$AppVersion = (Get-Date -Format "yyyy.MM.dd")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$RootDir          = (Resolve-Path "$PSScriptRoot\..").Path
$AppName          = if ($env:APP_NAME)          { $env:APP_NAME }          else { "MobiTouchRobots" }
$BundleId         = if ($env:BUNDLE_ID)         { $env:BUNDLE_ID }         else { "net.mobitouch.robots" }
$SignApp          = if ($env:SIGN_APP)           { $env:SIGN_APP }          else { "0" }
$SignIdentity     = if ($env:SIGN_IDENTITY)      { $env:SIGN_IDENTITY }     else { "" }
$InstallBuildDeps = if ($env:INSTALL_BUILD_DEPS) { $env:INSTALL_BUILD_DEPS } else { "1" }
$FailOnSignError  = if ($env:FAIL_ON_SIGN_ERROR) { $env:FAIL_ON_SIGN_ERROR } else { "0" }

$IconSourcePng  = Join-Path $RootDir "app_icon.png"
$BuildRoot      = Join-Path $RootDir "build\windows-package-pyinstaller"
$DistRoot       = Join-Path $RootDir "dist\windows"
$PyiDistDir     = Join-Path $BuildRoot "pyi-dist"
$ExeDir         = Join-Path $PyiDistDir $AppName
$ZipFile        = Join-Path $DistRoot "${AppName}-${AppVersion}-pyinstaller.zip"
$IconFile       = Join-Path $BuildRoot "AppIcon.ico"
$LauncherScript = Join-Path $BuildRoot "pyinstaller_launcher.py"
$PythonExe      = Join-Path $RootDir ".venv\Scripts\python.exe"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Require-Cmd([string]$Cmd) {
    if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
        Write-Error "Missing required command: $Cmd"
        exit 1
    }
}

function Find-Signtool {
    # Search common Windows SDK installation paths for signtool.exe
    $sdkBases = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "${env:ProgramFiles}\Windows Kits\10\bin"
    )
    foreach ($base in $sdkBases) {
        if (Test-Path $base) {
            $found = Get-ChildItem -Path $base -Recurse -Filter "signtool.exe" `
                     -ErrorAction SilentlyContinue |
                     Sort-Object FullName -Descending |
                     Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    # Fall back to PATH
    $inPath = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($inPath) { return $inPath.Source }
    return $null
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
Write-Host "==> Validating prerequisites"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Expected Python executable not found: $PythonExe`nCreate/setup .venv first, then run this script again."
    exit 1
}

Require-Cmd "git"

# Confirm we are building on Windows x64
$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ($arch -ne [System.Runtime.InteropServices.Architecture]::X64) {
    Write-Error "This packaging script targets x64 builds only.`nCurrent architecture: $arch`nRun on a Windows x64 machine."
    exit 1
}

# ---------------------------------------------------------------------------
# Ensure PyInstaller is available
# ---------------------------------------------------------------------------
Write-Host "==> Ensuring PyInstaller is available in .venv"
$pyiCheck = & $PythonExe -m PyInstaller --version 2>&1
if ($LASTEXITCODE -ne 0) {
    & $PythonExe -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# ---------------------------------------------------------------------------
# Install build dependencies
# ---------------------------------------------------------------------------
if ($InstallBuildDeps -eq "1") {
    Write-Host "==> Installing build dependencies into .venv"
    & $PythonExe -m pip install --upgrade pip setuptools wheel
    & $PythonExe -m pip install --only-binary=av "av>=14.0.0,<15.0.0"
    & $PythonExe -m pip install git+https://github.com/legion1581/unitree_webrtc_connect.git@v2.0.4
    & $PythonExe -m pip install moderngl Pillow PyQt5
    & $PythonExe -m pip install pywavefront
    & $PythonExe -m pip install pygame
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# ---------------------------------------------------------------------------
# Locate wasmtime Windows DLL
# ---------------------------------------------------------------------------
$WasmtimeDllPattern = Join-Path $RootDir ".venv\Lib\site-packages\wasmtime\windows-x86_64\wasmtime.dll"
if (-not (Test-Path $WasmtimeDllPattern)) {
    # Fallback: search all wasmtime subdirs for any .dll
    $wasmtimeBase = Join-Path $RootDir ".venv\Lib\site-packages\wasmtime"
    $WasmtimeDllFound = Get-ChildItem -Path $wasmtimeBase -Recurse -Filter "*.dll" `
                         -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $WasmtimeDllFound) {
        Write-Error "Expected wasmtime DLL not found under: $wasmtimeBase`nEnsure wasmtime is installed in .venv before packaging."
        exit 1
    }
    $WasmtimeDllSrc        = $WasmtimeDllFound.FullName
    $WasmtimeDllDestSubdir = $WasmtimeDllFound.DirectoryName.Replace(
        (Join-Path $RootDir ".venv\Lib\site-packages\"), "")
} else {
    $WasmtimeDllSrc        = $WasmtimeDllPattern
    $WasmtimeDllDestSubdir = "wasmtime\windows-x86_64"
}

# ---------------------------------------------------------------------------
# Prepare build directories
# ---------------------------------------------------------------------------
Write-Host "==> Preparing build directories"
if (Test-Path $BuildRoot) { Remove-Item $BuildRoot -Recurse -Force }
New-Item -ItemType Directory -Path $BuildRoot | Out-Null
New-Item -ItemType Directory -Path $DistRoot  -Force | Out-Null

# ---------------------------------------------------------------------------
# Build app icon (.ico)
# ---------------------------------------------------------------------------
Write-Host "==> Building app icon (.ico)"
if (-not (Test-Path $IconSourcePng)) {
    Write-Error "Expected icon source not found: $IconSourcePng"
    exit 1
}

$iconScript = @"
from PIL import Image
img = Image.open(r"$IconSourcePng").convert("RGBA")
sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
img.save(r"$IconFile", format="ICO", sizes=sizes)
print("Icon saved:", r"$IconFile")
"@

& $PythonExe -c $iconScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to generate .ico file. Is Pillow installed?"
    exit 1
}

# ---------------------------------------------------------------------------
# Write PyInstaller launcher
# ---------------------------------------------------------------------------
Write-Host "==> Writing PyInstaller launcher"

@'
from __future__ import annotations

import os
import platform
import runpy
import sys
from pathlib import Path


def show_error(message: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, message, "MobiTouchRobots", 0x10  # MB_ICONERROR
        )
    except Exception:
        pass


def fail(message: str, log_file: Path) -> int:
    print(f"[ERROR] {message}", file=sys.stderr)
    show_error(f"{message}\n\nLog file: {log_file}")
    return 1


def main() -> int:
    log_dir = Path.home() / "AppData" / "Local" / "MobiTouchRobots" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "launcher-pyinstaller.log"

    with log_file.open("a", encoding="utf-8") as fh:
        fh.write("==== MobiTouchRobots (PyInstaller) launch ====\n")
        fh.write(f"EXE={Path(sys.executable).resolve()}\n")

    machine = platform.machine().lower()

    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"HOST_ARCH={machine}\n")

    if machine not in ("amd64", "x86_64"):
        return fail(
            f"This build targets x86_64/AMD64 only.\nDetected architecture: {machine}",
            log_file,
        )

    os.environ.setdefault("UI", "qt")
    os.environ["PYTHONUNBUFFERED"] = "1"

    sys.argv = [sys.argv[0], *sys.argv[1:]]
    runpy.run_module("src", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@ | Set-Content -Path $LauncherScript -Encoding UTF8

# ---------------------------------------------------------------------------
# Run PyInstaller
# ---------------------------------------------------------------------------
Write-Host "==> Building .exe with PyInstaller"

# On Windows PyInstaller uses ';' as the src:dest separator for --add-data / --add-binary
& $PythonExe -m PyInstaller `
    --noconfirm `
    --windowed `
    --paths "$RootDir" `
    --name "$AppName" `
    --icon "$IconFile" `
    --hidden-import "src.__main__" `
    --collect-submodules src `
    --collect-all av `
    --collect-all aiortc `
    --collect-all unitree_webrtc_connect `
    --collect-all wasmtime `
    --collect-all pygame `
    "--add-binary" "${WasmtimeDllSrc};${WasmtimeDllDestSubdir}" `
    "--add-data" "${RootDir}\logo.png;." `
    "--add-data" "${RootDir}\src\ui\controller_mapping_defaults.json;src/ui" `
    "--add-data" "${RootDir}\src\ui\controller.png;src/ui" `
    "--add-data" "${RootDir}\src\ui\keyboard.png;src/ui" `
    "--add-data" "${RootDir}\src\robot\robot_go2.png;src/robot" `
    --distpath "$PyiDistDir" `
    --workpath "$BuildRoot\pyi-build" `
    --specpath "$BuildRoot" `
    "$LauncherScript"

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit 1
}

if (-not (Test-Path $ExeDir)) {
    Write-Error "PyInstaller did not produce expected output directory: $ExeDir"
    exit 1
}

# ---------------------------------------------------------------------------
# Optional code signing
# ---------------------------------------------------------------------------
$SignedOk = 0
if ($SignApp -eq "1") {
    Write-Host "==> Signing executable with signtool"
    $Signtool = Find-Signtool
    if ($null -eq $Signtool) {
        Write-Warning "signtool.exe not found. Skipping code signing."
        if ($FailOnSignError -eq "1") {
            Write-Error "FAIL_ON_SIGN_ERROR=1, aborting."
            exit 1
        }
    } else {
        $exeFile = Join-Path $ExeDir "${AppName}.exe"
        $signArgs = @("sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256")
        if ($SignIdentity -ne "") {
            $signArgs += @("/n", $SignIdentity)
        }
        $signArgs += $exeFile

        & $Signtool @signArgs
        if ($LASTEXITCODE -eq 0) {
            $SignedOk = 1
        } else {
            Write-Warning "Code signing failed."
            if ($FailOnSignError -eq "1") {
                Write-Error "FAIL_ON_SIGN_ERROR=1, aborting."
                exit 1
            }
            Write-Warning "Continuing to ZIP creation without a valid executable signature."
        }
    }
} else {
    Write-Host "Skipping codesign (SIGN_APP=$SignApp)."
}

# ---------------------------------------------------------------------------
# Package into ZIP archive
# ---------------------------------------------------------------------------
Write-Host "==> Building ZIP archive"
if (Test-Path $ZipFile) { Remove-Item $ZipFile -Force }

Compress-Archive -Path "$ExeDir\*" -DestinationPath $ZipFile -CompressionLevel Optimal

Write-Host ""
Write-Host "Done."
Write-Host "Executable dir : $ExeDir"
Write-Host "ZIP archive    : $ZipFile"
Write-Host "Target         : Windows x64"
Write-Host "Mode           : Pure PyInstaller frozen exe"
Write-Host "Signed         : $SignApp"
Write-Host "Identity       : $SignIdentity"
Write-Host "Sign ok        : $SignedOk"
