#!/bin/bash
# The packaged Lastbook desktop app for Windows: one folder, unsigned, with no open port. Run in Git Bash on Windows:
#
#   PY=/c/path/to/python.exe OUT='C:\path\to\output' bash packaging/build_app_windows.sh
#
# PY         CPython 3.12 with packaging/requirements_app.txt installed. It is run isolated and nothing is installed.
# OUT        Build output: dist\Lastbook\Lastbook.exe, work\, and the logs. Defaults to build-app\ beside packaging\.
# WEBVIEW2   Folder with the three Microsoft files below, from the NuGet package Microsoft.Web.WebView2 1.0.3856.49
#            (win-x64 loader). Defaults to app\webview2\. They are checked against the hashes here.
# LLM        Folder with lastbook-llm.exe and its DLLs, from packaging/llm/build_llm_windows.sh. Defaults to derived\llm\bin-win.
#            It goes to _internal\llm as it is, and its SHA256SUMS.txt is checked first. The model itself never ships.
# SCAN_TERMS Optional text file of words that must not appear in the package, one a line: machine names, user names.
#            It stays out of the repository, because the list itself names them.
#
# app/tests is never on the search path. The build fails if the scan finds test code or anything else that must stay out.
set -euo pipefail
HERE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
ROOT="$(realpath "$HERE/..")"
ROOTW="$(cygpath -w "$ROOT")"
PY="${PY:?Set PY to a CPython 3.12 python.exe}"
OUT="${OUT:-$ROOTW\\build-app}"
WEBVIEW2="${WEBVIEW2:-$ROOTW\\app\\webview2}"
LLM="${LLM:-$ROOTW\\derived\\llm\\bin-win}"
OUTU="$(cygpath -u "$OUT")"
( cd "$(cygpath -u "$LLM")" && sha256sum --quiet -c SHA256SUMS.txt ) || { echo "the runner in $LLM does not match its SHA256SUMS.txt" >&2; exit 1; }
mkdir -p "$OUTU/tmp/localappdata" "$OUTU/tmp/pyinstaller"

# Everything the build tool caches stays in the output folder, and no bytecode lands beside the sources.
export TEMP="$OUT\\tmp" TMP="$OUT\\tmp" LOCALAPPDATA="$OUT\\tmp\\localappdata" PYINSTALLER_CONFIG_DIR="$OUT\\tmp\\pyinstaller"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0
unset PYTHONHOME PYTHONPATH

check_hash() {
  local got
  got="$(sha256sum "$(cygpath -u "$WEBVIEW2")/$2" | cut -d' ' -f1)"
  if [ "$got" != "$1" ]; then
    echo "$2 in $WEBVIEW2 is not the expected file: $got" >&2
    exit 1
  fi
}
check_hash 8219a3135436c147f8eb02fb831e99596103eebc18b6d7b794ca93f4c67018a2 Microsoft.Web.WebView2.Core.dll
check_hash c48f8d729dc531288d2c53a6241effe7922ed1b947850b2442008a945c098c48 Microsoft.Web.WebView2.WinForms.dll
check_hash eb5335edeaa6f2122c044e82aab2351dc8c9b4e0fe5e578c71922fb61be285e7 WebView2Loader.dll

# Pinned versions, read from what is installed, not what pip would fetch.
"$PY" -I -B - "$ROOTW\\packaging\\requirements_app.txt" <<'PYCHECK'
import importlib.metadata as m, re, sys
bad = []
for line in open(sys.argv[1], encoding='utf-8'):
    line = line.split('#')[0].strip()
    if line:
        name, want = re.split('==', line.split(';')[0].strip())
        try:
            have = m.version(name)
        except m.PackageNotFoundError:
            have = 'missing'
        if have != want:
            bad.append(f'{name}: want {want}, have {have}')
if sys.version_info[:2] != (3, 12):
    bad.append(f'python: want 3.12, have {sys.version.split()[0]}')
sys.exit('\n'.join(bad) if bad else 0)
PYCHECK

# web/ and content/ as they ship, not the source folders: see ship_edits.json
"$PY" -I -B "$ROOTW\\packaging\\ship_app_files.py" "$OUT\\ship"

"$PY" -I -B -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name Lastbook --icon NONE \
  --distpath "$OUT\\dist" --workpath "$OUT\\work" --specpath "$OUT" \
  --paths "$ROOTW\\app" --paths "$ROOTW" \
  --add-data "$OUT\\ship\\web;web" --add-data "$OUT\\ship\\content;content" \
  --add-data "$WEBVIEW2\\Microsoft.Web.WebView2.Core.dll;webview2" \
  --add-data "$WEBVIEW2\\Microsoft.Web.WebView2.WinForms.dll;webview2" \
  --add-data "$WEBVIEW2\\WebView2Loader.dll;webview2" \
  --add-data "$LLM;llm" \
  --hidden-import server --hidden-import retrieval --hidden-import assistant --hidden-import llm_local \
  --hidden-import engine.paths --hidden-import engine.library --hidden-import engine.saved_pages --hidden-import engine.quiet_onnx \
  --hidden-import bridge --hidden-import shell_windows --hidden-import clr --hidden-import _cffi_backend \
  --exclude-module shell_macos --exclude-module remote_storage --exclude-module tests \
  --exclude-module webview --exclude-module bottle --exclude-module proxy_tools --exclude-module lastbook_launcher \
  --exclude-module tkinter --exclude-module pytest --exclude-module unittest --exclude-module doctest --exclude-module pdb \
  --exclude-module numpy.tests --exclude-module numpy.testing --exclude-module numpy._core._multiarray_tests --exclude-module numpy.f2py \
  --exclude-module PyInstaller --exclude-module altgraph --exclude-module pefile --exclude-module setuptools --exclude-module pkg_resources \
  --exclude-module _distutils_hack --exclude-module yaml --exclude-module pypdfium2_cli \
  --collect-all libzim --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all clr_loader --collect-all pythonnet \
  --collect-binaries onnxruntime --collect-binaries tokenizers \
  --python-option "X utf8" \
  "$ROOTW\\app\\main.py"

DIST="$OUT\\dist\\Lastbook"
cp "$HERE/Lastbook.exe.config" "$(cygpath -u "$DIST")/Lastbook.exe.config"    # without it, a downloaded copy cannot open its window
"$PY" -I -B "$ROOTW\\packaging\\scan_app_package.py" "$DIST" ${SCAN_TERMS:+--terms "$SCAN_TERMS"} --report "$OUT\\package-scan.json"
du -sh "$(cygpath -u "$DIST")"
sha256sum "$(cygpath -u "$DIST")/Lastbook.exe"
