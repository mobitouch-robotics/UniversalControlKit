#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="${APP_NAME:-UniversalControlKit}"
BUNDLE_ID="${BUNDLE_ID:-net.mobitouch.universalcontrolkit}"
APP_VERSION="${1:-$(date +%Y.%m.%d)}"
SIGN_APP="${SIGN_APP:-1}"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"
SIGN_HARDENED_RUNTIME="${SIGN_HARDENED_RUNTIME:-0}"
INSTALL_BUILD_DEPS="${INSTALL_BUILD_DEPS:-1}"
FAIL_ON_SIGN_ERROR="${FAIL_ON_SIGN_ERROR:-0}"
ICON_SOURCE_PNG="$ROOT_DIR/app_icon.png"

BUILD_ROOT="$ROOT_DIR/build/macos-package-pyinstaller"
DIST_ROOT="$ROOT_DIR/dist/macos"
PYI_DIST_DIR="$BUILD_ROOT/pyi-dist"
APP_DIR="$PYI_DIST_DIR/${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
DMG_FILE="$DIST_ROOT/${APP_NAME}-${APP_VERSION}-pyinstaller.dmg"
ICONSET_DIR="$BUILD_ROOT/AppIcon.iconset"
ICNS_FILE="$BUILD_ROOT/AppIcon.icns"
LAUNCHER_SCRIPT="$BUILD_ROOT/pyinstaller_launcher.py"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

quiet_xattr_clear_all() {
  local target_path="$1"
  xattr -rc "$target_path" >/dev/null 2>&1 || true
}

quiet_xattr_remove_provenance() {
  local target_path="$1"
  xattr -dr com.apple.provenance "$target_path" >/dev/null 2>&1 || true
}

is_macho_file() {
  local target_file="$1"
  file "$target_file" | grep -q "Mach-O"
}

codesign_single() {
  local target="$1"
  if [[ "$SIGN_IDENTITY" == "-" ]]; then
    codesign --force --sign - --timestamp=none "$target"
  else
    codesign --force --sign "$SIGN_IDENTITY" --timestamp "$target"
  fi
}

echo "==> Validating prerequisites"
require_cmd rsync
require_cmd hdiutil
require_cmd sips
require_cmd iconutil
require_cmd codesign
require_cmd xattr
require_cmd git

HOST_ARCH="$(uname -m)"
if [[ "$HOST_ARCH" != "arm64" ]]; then
  echo "This packaging script is configured for arm64-only builds." >&2
  echo "Current host architecture: $HOST_ARCH" >&2
  echo "Run packaging on an Apple Silicon Mac (arm64)." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  echo "Expected Python executable not found: $ROOT_DIR/.venv/bin/python" >&2
  echo "Create/setup .venv first, then run this script again." >&2
  exit 1
fi

echo "==> Ensuring PyInstaller is available in .venv"
if ! "$ROOT_DIR/.venv/bin/python" -m PyInstaller --version >/dev/null 2>&1; then
  "$ROOT_DIR/.venv/bin/python" -m pip install pyinstaller
fi

if [[ "$INSTALL_BUILD_DEPS" == "1" ]]; then
  echo "==> Installing build dependencies into $ROOT_DIR/.venv"
  "$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
  "$ROOT_DIR/.venv/bin/python" -m pip install --only-binary=av 'av>=14.0.0,<15.0.0'
  "$ROOT_DIR/.venv/bin/python" -m pip install git+https://github.com/legion1581/unitree_webrtc_connect.git@v2.0.4
  "$ROOT_DIR/.venv/bin/python" -m pip install moderngl Pillow PyQt5
  "$ROOT_DIR/.venv/bin/python" -m pip install pywavefront
  "$ROOT_DIR/.venv/bin/python" -m pip install pygame
fi

WASMTIME_DYLIB_SRC="$ROOT_DIR/.venv/lib/python3.13/site-packages/wasmtime/darwin-aarch64/_libwasmtime.dylib"
if [[ ! -f "$WASMTIME_DYLIB_SRC" ]]; then
  echo "Expected wasmtime dylib not found: $WASMTIME_DYLIB_SRC" >&2
  echo "Ensure wasmtime is installed in $ROOT_DIR/.venv before packaging." >&2
  exit 1
fi

echo "==> Preparing build directories"
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT" "$DIST_ROOT"

echo "==> Building app icon (.icns)"
if [[ ! -f "$ICON_SOURCE_PNG" ]]; then
  echo "Expected icon source not found: $ICON_SOURCE_PNG" >&2
  exit 1
fi

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

sips -z 16 16     "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32     "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32     "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64     "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128   "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256   "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256   "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512   "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512   "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$ICON_SOURCE_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null

iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"

echo "==> Writing PyInstaller launcher"
cat > "$LAUNCHER_SCRIPT" <<'PYEOF'
from __future__ import annotations

import os
import platform
import runpy
import subprocess
import sys
from pathlib import Path


def show_error(message: str) -> None:
    script = f'display alert "UniversalControlKit failed to start" message "{message}"'
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], check=False)
    except Exception:
        pass


def fail(message: str, log_file: Path) -> int:
    print(f"[ERROR] {message}", file=sys.stderr)
    show_error(f"{message}\\n\\nLog file: {log_file}")
    return 1


def main() -> int:
    log_dir = Path.home() / "Library" / "Logs" / "UniversalControlKit"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "launcher-pyinstaller.log"

    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"==== UniversalControlKit (PyInstaller) launch ====\\n")
        fh.write(f"EXE={Path(sys.executable).resolve()}\\n")

    machine = platform.machine()
    if machine == "x86_64":
        has_arm64 = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if has_arm64 == "1":
            os.execv("/usr/bin/arch", ["arch", "-arm64", sys.executable, *sys.argv])

    if platform.machine() != "arm64":
        return fail("This build is arm64-only. Please run it on Apple Silicon.", log_file)

    os.environ.setdefault("UI", "qt")
    os.environ["PYTHONUNBUFFERED"] = "1"

    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"HOST_ARCH={platform.machine()}\\n")

    sys.argv = [sys.argv[0], *sys.argv[1:]]
    runpy.run_module("src", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYEOF

echo "==> Building .app with PyInstaller"
"$ROOT_DIR/.venv/bin/python" -m PyInstaller \
  --noconfirm \
  --windowed \
  --paths "$ROOT_DIR" \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --icon "$ICNS_FILE" \
  --hidden-import src.__main__ \
  --collect-submodules src \
  --collect-all av \
  --collect-all aiortc \
  --collect-all unitree_webrtc_connect \
  --collect-all wasmtime \
  --collect-all pygame \
  --hidden-import PyQt5.QtSvg \
  --add-binary "$WASMTIME_DYLIB_SRC:wasmtime/darwin-aarch64" \
  --add-data "$ROOT_DIR/logo.png:." \
  --add-data "$ROOT_DIR/src/ui/controller_mapping_defaults.json:src/ui" \
  --add-data "$ROOT_DIR/src/ui/controller.png:src/ui" \
  --add-data "$ROOT_DIR/src/ui/keyboard.png:src/ui" \
  --add-data "$ROOT_DIR/src/ui/dualsense-svgrepo-com.svg:src/ui" \
  --add-data "$ROOT_DIR/src/ui/gamecontroller-fill-svgrepo-com.svg:src/ui" \
  --add-data "$ROOT_DIR/src/ui/keyboard-shortcuts-svgrepo-com.svg:src/ui" \
  --add-data "$ROOT_DIR/src/robot/robot_go2.png:src/robot" \
  --distpath "$PYI_DIST_DIR" \
  --workpath "$BUILD_ROOT/pyi-build" \
  --specpath "$BUILD_ROOT" \
  "$LAUNCHER_SCRIPT"

if [[ ! -d "$APP_DIR" ]]; then
  echo "PyInstaller did not produce app bundle: $APP_DIR" >&2
  exit 1
fi

echo "==> Applying ad-hoc code signature"
SIGNED_OK=0
if [[ "$SIGN_APP" == "1" ]]; then
  if {
    # Remove problematic provenance attributes and stale signatures introduced by
    # previous signed artifacts before re-signing the final app bundle.
    quiet_xattr_remove_provenance "$APP_DIR"
    quiet_xattr_clear_all "$APP_DIR"
    chmod -R u+w "$APP_DIR" || true
    codesign --remove-signature "$APP_DIR" 2>/dev/null || true

    while IFS= read -r -d '' maybe_macho; do
      if is_macho_file "$maybe_macho"; then
        codesign --remove-signature "$maybe_macho" 2>/dev/null || true
      fi
    done < <(find "$APP_DIR" -type f -print0)

    # Sign all Mach-O files first, then sign bundle container.
    while IFS= read -r -d '' maybe_macho; do
      if is_macho_file "$maybe_macho"; then
        codesign_single "$maybe_macho"
      fi
    done < <(find "$APP_DIR/Contents" -type f -print0)

    if [[ "$SIGN_IDENTITY" == "-" ]]; then
      codesign --force --deep --sign - --timestamp=none "$APP_DIR"
    else
      SIGN_ARGS=(--force --deep --sign "$SIGN_IDENTITY" --timestamp)
      if [[ "$SIGN_HARDENED_RUNTIME" == "1" ]]; then
        SIGN_ARGS+=(--options runtime)
      fi
      codesign "${SIGN_ARGS[@]}" "$APP_DIR"
    fi
    codesign --verify --deep --strict --verbose=2 "$APP_DIR"
  }; then
    SIGNED_OK=1
  else
    echo "[WARN] Code signing failed."
    if [[ "$FAIL_ON_SIGN_ERROR" == "1" ]]; then
      echo "[ERROR] FAIL_ON_SIGN_ERROR=1, aborting." >&2
      exit 1
    fi
    echo "[WARN] Continuing to DMG creation without a valid app signature."
  fi
else
  echo "Skipping codesign (SIGN_APP=$SIGN_APP)."
fi

echo "==> Building DMG"
rm -f "$DMG_FILE"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$APP_DIR" \
  -ov \
  -format UDZO \
  "$DMG_FILE"

echo ""
echo "Done."
echo "App bundle: $APP_DIR"
echo "DMG file : $DMG_FILE"
echo "Target   : arm64"
echo "Mode     : Pure PyInstaller frozen app"
echo "Signed   : $SIGN_APP"
echo "Identity : $SIGN_IDENTITY"
echo "Sign ok  : $SIGNED_OK"
