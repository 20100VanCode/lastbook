#!/bin/bash
# Builds Lastbook.app for Apple Silicon. Needs uv. Run from anywhere:
#   bash packaging/build_app_macos.sh
#
# Each build gets a new folder, derived/app-build/mac/<date-time>/, so nothing ever has to be removed.
# derived/app-build/mac/Lastbook.app points at the newest good one.
# The app is ad-hoc signed by the build tool and nothing more: no certificate, no notarization.
# Optional: put one word per line in derived/app-build/scan-terms.txt (machine names, user names) and the scan refuses a package holding any.
set -euo pipefail
HERE="$(dirname "$(/bin/realpath "$0")")"
ROOT="$(dirname "$HERE")"
BUILD="$ROOT/derived/app-build"
VENV="$BUILD/mac-venv"
OUT="$BUILD/mac/$(date +%Y%m%d-%H%M%S)"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$BUILD/mac/pycache"
export PYINSTALLER_CONFIG_DIR="$BUILD/mac/pyinstaller-cache"
if [ "$(uname -m)" != arm64 ]; then
  echo "This build is for Apple Silicon." >&2
  exit 1
fi
mkdir -p "$OUT"
[ -x "$VENV/bin/python" ] || uv venv --python 3.11 "$VENV"
uv pip install --python "$VENV/bin/python" -r "$HERE/requirements_macos.txt"
"$VENV/bin/python" -I -B "$HERE/ship_app_files.py" "$OUT/ship"   # web/ and content/ as they ship: see ship_edits.json
# What setup can install (docs/SETUP-API.md): the packs publish-packs has verified, with Small from the 1.0.0 release, and the model
"$VENV/bin/python" -I -B "$HERE/release_manifest.py" --small-from "$ROOT/derived/release/1.0.0-20261104-1507" --out "$OUT/ship/setup/manifest-v1.json"
export LASTBOOK_SHIP="$OUT/ship"
"$VENV/bin/python" -m PyInstaller --noconfirm --distpath "$OUT/dist" --workpath "$OUT/work" "$HERE/lastbook_macos.spec" 2>&1 | tee "$OUT/build.log"
BUNDLE="$OUT/dist/Lastbook.app"
"$VENV/bin/python" "$HERE/scan_package_macos.py" "$BUNDLE" --terms-file "$BUILD/scan-terms.txt" | tee "$OUT/scan.txt"
codesign --verify --deep --strict "$BUNDLE"
ln -sfn "$BUNDLE" "$BUILD/mac/Lastbook.app"
du -sh "$BUNDLE"
echo "Built: $BUNDLE"
