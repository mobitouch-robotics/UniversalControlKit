#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="${APP_NAME:-MobiTouchRobots}"
BUNDLE_ID="${BUNDLE_ID:-net.mobitouch.robots}"
APP_VERSION="${1:-$(date +%Y.%m.%d)}"
ICON_SOURCE_PNG="$ROOT_DIR/app_icon.png"

BUILD_ROOT="$ROOT_DIR/build/macos-package"
DIST_ROOT="$ROOT_DIR/dist/macos"
APP_DIR="$BUILD_ROOT/${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
PAYLOAD_DIR="$RESOURCES_DIR/MobiTouchRobots"
DMG_STAGING_DIR="$BUILD_ROOT/dmg-staging"
DMG_FILE="$DIST_ROOT/${APP_NAME}-${APP_VERSION}.dmg"
ICONSET_DIR="$BUILD_ROOT/AppIcon.iconset"
ICNS_FILE="$RESOURCES_DIR/AppIcon.icns"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

echo "==> Validating prerequisites"
require_cmd rsync
require_cmd hdiutil
require_cmd sips
require_cmd iconutil
require_cmd otool
require_cmd install_name_tool
require_cmd codesign
require_cmd xattr

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

echo "==> Preparing build directories"
rm -rf "$BUILD_ROOT"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$DIST_ROOT"

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

echo "==> Copying application payload (including .venv)"
rsync -a \
  --exclude ".git" \
  --exclude ".github" \
  --exclude ".DS_Store" \
  --exclude "dist" \
  --exclude "build" \
  --exclude "build-dir" \
  --exclude ".flatpak-builder" \
  --exclude "*.pyc" \
  --exclude "__pycache__" \
  "$ROOT_DIR/" "$PAYLOAD_DIR/"

# Strip inherited xattrs from copied payload to avoid write failures when
# patching Mach-O binaries (install_name_tool creates temp outputs).
xattr -rc "$PAYLOAD_DIR" || true

echo "==> Materializing bundled Python executable"
VENV_BIN_DIR="$PAYLOAD_DIR/.venv/bin"
if [[ -d "$VENV_BIN_DIR" ]]; then
  PY_VERSIONED_LINK="$(find "$VENV_BIN_DIR" -maxdepth 1 -type l -name 'python3.*' | head -n 1 || true)"
  if [[ -n "$PY_VERSIONED_LINK" ]]; then
    PY_TARGET="$(readlink "$PY_VERSIONED_LINK" || true)"
    if [[ -n "$PY_TARGET" && "$PY_TARGET" == /* && -x "$PY_TARGET" ]]; then
      rm -f "$PY_VERSIONED_LINK"
      cp "$PY_TARGET" "$PY_VERSIONED_LINK"
      chmod +x "$PY_VERSIONED_LINK"
      ln -sf "$(basename "$PY_VERSIONED_LINK")" "$VENV_BIN_DIR/python"
      ln -sf "$(basename "$PY_VERSIONED_LINK")" "$VENV_BIN_DIR/python3"
    fi
  fi
fi

echo "==> Bundling Python framework runtime"
if [[ -d "$VENV_BIN_DIR" ]]; then
  PY_VERSIONED_BIN="$(find "$VENV_BIN_DIR" -maxdepth 1 -type f -name 'python3.*' | head -n 1 || true)"
  if [[ -n "$PY_VERSIONED_BIN" ]]; then
    PY_DYLIB="$(otool -L "$PY_VERSIONED_BIN" | awk 'NR==2 {print $1}')"
    if [[ -n "$PY_DYLIB" && "$PY_DYLIB" == /* && -f "$PY_DYLIB" ]]; then
      PY_FRAMEWORK_VERSION_DIR="$(dirname "$PY_DYLIB")"
      BUNDLED_FRAMEWORK_DIR="$RESOURCES_DIR/Python.framework/Versions/$(basename "$PY_FRAMEWORK_VERSION_DIR")"
      mkdir -p "$(dirname "$BUNDLED_FRAMEWORK_DIR")"
      rm -rf "$BUNDLED_FRAMEWORK_DIR"
      cp -R -X "$PY_FRAMEWORK_VERSION_DIR" "$BUNDLED_FRAMEWORK_DIR"
      xattr -rc "$BUNDLED_FRAMEWORK_DIR" || true
      find "$BUNDLED_FRAMEWORK_DIR" -type l ! -exec test -e {} \; -delete

      BUNDLED_PY_DYLIB="@executable_path/../../Resources/Python.framework/Versions/$(basename "$PY_FRAMEWORK_VERSION_DIR")/Python"

      # Relink venv binaries/modules that reference the absolute host Python framework.
      while IFS= read -r target_file; do
        if otool -L "$target_file" 2>/dev/null | grep -qF "$PY_DYLIB"; then
          install_name_tool -change "$PY_DYLIB" "$BUNDLED_PY_DYLIB" "$target_file" || true
        fi
      done < <(find "$PAYLOAD_DIR/.venv" -type f \( -name "*.so" -o -name "python3.*" -o -name "python" -o -name "python3" \))
    fi
  fi
fi

echo "==> Normalizing bundled venv metadata"
PYVENV_CFG="$PAYLOAD_DIR/.venv/pyvenv.cfg"
if [[ -f "$PYVENV_CFG" ]]; then
  # Remove machine-specific absolute project path from venv metadata and keep
  # only base interpreter hints used for diagnostics.
  awk '
    /^command = / { print "command = packaged"; next }
    { print }
  ' "$PYVENV_CFG" > "$PYVENV_CFG.tmp"
  mv "$PYVENV_CFG.tmp" "$PYVENV_CFG"
fi

echo "==> Writing launcher"
cat > "$MACOS_DIR/$APP_NAME" <<'EOF'
#!/usr/bin/env bash
set -u -o pipefail

APP_ROOT="$(cd "$(dirname "$0")/../Resources/MobiTouchRobots" && pwd)"
export UI=qt
export PYTHONUNBUFFERED=1

LOG_DIR="$HOME/Library/Logs/MobiTouchRobots"
LOG_FILE="$LOG_DIR/launcher.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec >>"$LOG_FILE" 2>&1

show_error() {
  local msg="$1"
  /usr/bin/osascript <<OSA >/dev/null 2>&1 || true
display alert "MobiTouchRobots failed to start" message "$msg"
OSA
}

fail() {
  local msg="$1"
  echo "[ERROR] $msg"
  show_error "$msg

Log file: $LOG_FILE"
  exit 1
}

echo "==== MobiTouchRobots launch $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
echo "APP_ROOT=$APP_ROOT"

cd "$APP_ROOT"
PY_BIN="$APP_ROOT/.venv/bin/python"
HOST_ARCH="$(uname -m)"
HAS_ARM64="$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || echo 0)"

# If the app was launched under Rosetta on Apple Silicon, re-exec natively first.
if [[ "$HOST_ARCH" == "x86_64" && "$HAS_ARM64" == "1" ]]; then
  exec /usr/bin/arch -arm64 "$0" "$@"
fi

if [[ "$HOST_ARCH" != "arm64" ]]; then
  fail "This build is arm64-only. Please run it on Apple Silicon."
fi

[[ -x "$PY_BIN" ]] || fail "Bundled Python executable not found at $PY_BIN"

PYVENV_CFG="$APP_ROOT/.venv/pyvenv.cfg"
if [[ -f "$PYVENV_CFG" ]]; then
  BASE_HOME="$(awk -F' = ' '/^home = /{print $2; exit}' "$PYVENV_CFG" || true)"
  if [[ -n "$BASE_HOME" && ! -d "$BASE_HOME" ]]; then
    echo "[WARN] Base runtime path from pyvenv.cfg not found: $BASE_HOME"
    echo "[WARN] Continuing launch attempt with bundled interpreter."
  fi
fi

echo "PY_BIN=$PY_BIN"
echo "HOST_ARCH=$HOST_ARCH HAS_ARM64=$HAS_ARM64"

run_python() {
  "$@"
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    fail "Python process exited with code $rc"
  fi
}

run_python "$PY_BIN" -m src "$@"
EOF
chmod +x "$MACOS_DIR/$APP_NAME"

echo "==> Writing Info.plist"
cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleExecutable</key>
  <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${APP_VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${APP_VERSION}</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>LSRequiresNativeExecution</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

echo "==> Applying ad-hoc code signature"
codesign --force --deep --sign - --timestamp=none "$APP_DIR"
codesign --verify --deep --strict --verbose=2 "$APP_DIR"

echo "==> Preparing DMG staging"
rm -rf "$DMG_STAGING_DIR"

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
