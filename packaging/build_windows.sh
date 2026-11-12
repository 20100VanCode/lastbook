#!/bin/bash
# One-folder Windows build, run in Git Bash on Windows:
#   PY=/c/path/to/python.exe OUT='C:\path\to\build' bash packaging/build_windows.sh
# PY is a CPython 3.12 with packaging/requirements.txt installed. OUT defaults to build\ beside packaging\.
# remote_storage is left out on purpose: the package holds no machine names or ssh code.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${PY:-python}"
ROOTW="$(cygpath -w "$ROOT")"
OUT="${OUT:-$ROOTW\\build}"
"$PY" -I -B "$ROOTW\\packaging\\ship_app_files.py" "$OUT\\ship"   # web/ and content/ as they ship: see ship_edits.json
"$PY" -m PyInstaller --noconfirm --clean --onedir --windowed --name Lastbook \
  --distpath "$OUT\\dist" --workpath "$OUT\\work" --specpath "$OUT" \
  --paths "$ROOTW" \
  --add-data "$OUT\\ship\\web;web" --add-data "$OUT\\ship\\content;content" \
  --hidden-import server --hidden-import retrieval --hidden-import assistant \
  --hidden-import engine.paths --hidden-import engine.library --hidden-import engine.saved_pages \
  --exclude-module remote_storage \
  --collect-all libzim --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all webview --collect-all clr_loader --collect-all pythonnet \
  --collect-binaries onnxruntime --collect-binaries tokenizers \
  --python-option "X utf8" \
  "$ROOTW\\packaging\\lastbook_launcher.py"
DIST="$(cygpath -u "$OUT\\dist\\Lastbook")"
CONTENTS="$("$PY" -m PyInstaller.utils.cliutils.archive_viewer --list --recursive --brief "$DIST/Lastbook.exe")"
if grep -q remote_storage <<<"$CONTENTS"; then
  echo "remote_storage got into the package" >&2
  exit 1
fi
"$PY" -I -B "$ROOTW\\packaging\\scan_app_package.py" "$OUT\\dist\\Lastbook" ${SCAN_TERMS:+--terms "$SCAN_TERMS"} --report "$OUT\\package-scan.json"   # the same scan as build_app_windows.sh; it refuses this older window (webview, lastbook_launcher)
du -sh "$DIST"
