#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="${APP_NAME:-UniversalControlKit}"
APP_VERSION="${1:-$(date +%Y.%m.%d)}"
DIST_ROOT="$ROOT_DIR/dist/macos"
BUILD_APP="$ROOT_DIR/build/macos-package-pyinstaller/pyi-dist/${APP_NAME}.app"
DMG_FILE="$DIST_ROOT/${APP_NAME}-${APP_VERSION}-pyinstaller.dmg"

SIGN_IDENTITY="${SIGN_IDENTITY:-}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

if [[ -z "$SIGN_IDENTITY" ]]; then
  echo "Missing SIGN_IDENTITY." >&2
  echo "Example: SIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'" >&2
  exit 1
fi

if [[ -z "$NOTARY_PROFILE" ]]; then
  echo "Missing NOTARY_PROFILE." >&2
  echo "Create it once with: xcrun notarytool store-credentials <profile-name> --apple-id <id> --team-id <team> --password <app-specific-password>" >&2
  exit 1
fi

require_cmd xcrun
require_cmd stapler
require_cmd spctl

echo "==> Building, signing (Developer ID), and creating DMG"
SIGN_APP=1 \
SIGN_IDENTITY="$SIGN_IDENTITY" \
SIGN_HARDENED_RUNTIME=1 \
bash "$ROOT_DIR/scripts/package-macos-dmg-pyinstaller.sh" "$APP_VERSION"

if [[ ! -f "$DMG_FILE" ]]; then
  echo "Expected DMG not found: $DMG_FILE" >&2
  exit 1
fi

if [[ ! -d "$BUILD_APP" ]]; then
  echo "Expected app not found: $BUILD_APP" >&2
  exit 1
fi

echo "==> Submitting DMG for notarization"
xcrun notarytool submit "$DMG_FILE" --keychain-profile "$NOTARY_PROFILE" --wait

echo "==> Stapling notarization ticket"
xcrun stapler staple "$BUILD_APP"
xcrun stapler staple "$DMG_FILE"

echo "==> Validating notarized artifacts"
xcrun stapler validate "$BUILD_APP"
xcrun stapler validate "$DMG_FILE"
spctl -a -vv -t open "$BUILD_APP" || true

echo ""
echo "Done."
echo "App bundle: $BUILD_APP"
echo "DMG file : $DMG_FILE"
echo "Signed with: $SIGN_IDENTITY"
echo "Notary profile: $NOTARY_PROFILE"
