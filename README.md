# Lastbook

Lastbook is an offline survival library for Mac and Windows. It puts manuals, videos, encyclopedias, an offline map and
short practical guides on one computer, and it keeps working with no internet at all. It starts from what a person needs
("Someone is hurt", "Get safe drinking water", "Power is out", "Find help nearby"). Then it shows a few hand-picked pages
with exact page numbers and each source's own limits, and after that the full manuals, videos and encyclopedias.

Website: <https://lastbook.org>. Contact: hello@lastbook.org.

> This repository is private for now. It will be opened later, under a licence that has not been chosen yet (see
> [LICENSE](LICENSE)).

## How it is built

- **Offline.** After setup, the app needs no network. Its windows block all web loads, the assistant talks only to a
  local program over pipes, and nothing is ever sent anywhere: no telemetry, no update check, no account.
- **No port.** The desktop app opens no network port. The window and the engine talk through an in-memory bridge
  (`app/bridge.py`): WKURLSchemeHandler on macOS (`app/shell_macos.py`), WebView2 `WebResourceRequested` on Windows
  (`app/shell_windows.py`). The local AI runner speaks JSON lines on standard input and output and opens no socket either.
- **One way out.** First-run setup (`engine/setup/`) is the only code that may reach the internet, and only when the
  person starts or resumes a download. It uses HTTPS to an allow-listed set of hosts and checks every file against the
  SHA-256 in the manifest. See [docs/SETUP-API.md](docs/SETUP-API.md).
- **A working library is never broken.** New data is unpacked beside the old one, checked, and then switched in with a
  single rename.

## What's where

| Path | What it is |
|---|---|
| `app/` | The desktop app: entry point (`main.py`), the no-port bridge, the macOS and Windows shells, and tests (`app/tests/`). |
| `engine/` | Paths and data-folder lookup, library access, saved pages, and first-run setup (`engine/setup/`). `engine/vendor-macos/` holds pypdfium2 for the Mac build. |
| `server.py`, `assistant.py`, `retrieval.py`, `llm_local.py` | The engine: request handler, the assistant and its citation checks, keyword plus meaning-based search, and the optional local AI. |
| `web/` | The interface, in plain HTML, CSS and JavaScript with no build step and nothing loaded from the web. `setup.*` is the first-run setup screen. |
| `content/` | The curated guides (`topics/*.json`) and what curators looked for and did not find (`gaps.json`). Format: `content/SCHEMA.md`. |
| `packaging/` | App builds (macOS and Windows), pack builder, release manifest, package scans, and `packaging/llm/` (the local AI runner). |
| `derived/packs/pack-spec.json` | What goes into each download pack (Small, Medium, All and add-ons). Everything else under `derived/` is generated and not kept here. |
| `tools/` | Builders for the offline map and place finder, plus curator helpers (`libq.py`, `validate_topics.py`). |
| `website/`, `website-next/` | The lastbook.org website: the current site and the next one, both static. |
| `docs/` | The setup contract (`SETUP-API.md`) and notes on the library server version (`LIBRARY-SERVER.md`). |

## Run from source

You need Python 3.11 or later and a **data folder**. A data folder holds `library-data/catalog.json` (the library) and gets
a `derived/` folder for indexes, caches and logs. Get one by running the app once and letting setup download a pack, or by
unzipping a pack from lastbook.org.

```bash
python3 -m venv .venv
.venv/bin/pip install -r packaging/requirements_macos.txt     # on Windows: packaging/requirements_app.txt
.venv/bin/python app/main.py --data /path/to/LastbookData
```

Without `--data`, the app looks in `LASTBOOK_DATA`, then the folder chosen last time, then `LastbookData` beside the
program, in Downloads, Documents or the home folder, and finally in the app's own data folder. If it finds none, it opens
setup. The full order is in `app/main.py`.

The **library server** version runs the same engine in a browser and can share with phones on the same Wi-Fi:

```bash
LASTBOOK_DATA=/path/to/LastbookData python3 server.py          # then open http://127.0.0.1:8890/
```

See [docs/LIBRARY-SERVER.md](docs/LIBRARY-SERVER.md). It was written for the household library this project grew out of,
so some of its paths and ports describe that setup.

## Build the apps

The builds write into `derived/app-build/` and refuse to finish if the package scan finds something that must not ship:
test code, a network call, a web address in our own pages, or a word from the private list (see below).

**macOS (Apple Silicon, needs [uv](https://github.com/astral-sh/uv)):**

```bash
bash packaging/llm/build_llm_macos.sh    # optional: the local AI runner, llama.cpp at a pinned tag, Metal
bash packaging/build_app_macos.sh        # Lastbook.app, ad-hoc signed, not notarized
```

**Windows (64-bit, in Git Bash):**

```bash
TOOLS='C:\path\to\tools' bash packaging/llm/build_llm_windows.sh                 # the runner: llama.cpp with Vulkan, CPU fallbacks
PY=/c/path/to/python.exe OUT='C:\path\to\output' bash packaging/build_app_windows.sh
```

`PY` is CPython 3.12 with `packaging/requirements_app.txt` installed. The script header lists each tool it needs, with its
version and checksum. The three WebView2 files come from the NuGet package `Microsoft.Web.WebView2` 1.0.3856.49 and are
checked against the hashes in `build_app_windows.sh`. `packaging/build_setup_windows.sh` builds the installer.

The Mac build reads the release manifest from a release folder under `derived/release/`, which is not in this repository;
see `packaging/release_manifest.py`.

## Packs and the local AI

- **Packs** are data folders: a library plus its catalog, search index and map. `packaging/build_packs.py` builds them
  from a frozen snapshot of a full library according to `derived/packs/pack-spec.json`, and `packaging/verify_packs.py` and
  `packaging/scan_pack.py` check them. The published packs are on `downloads.lastbook.org`. Setup downloads the one the
  person picks and checks it against `setup/manifest-v1.json`, which `packaging/release_manifest.py` writes at build time.
- **The local AI** is optional: Gemma 4 26B A4B (Unsloth's `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, about 17 GB). The file
  name, size, SHA-256 and Hugging Face revision are pinned in `llm_local.py`. Setup downloads it directly from Hugging
  Face, and only on computers where llama.cpp's own measurement says it fits. The model is never part of the app or of
  this repository. The runner is our own small program (`packaging/llm/lastbook_llm.cpp`) on llama.cpp.
- **Meaning-based search** uses BAAI's bge-small-en-v1.5 (ONNX) through onnxruntime, on Windows only; the Mac build uses
  keyword search.

## What is not in this repository, and why

- **The library** (`library-data/`): hundreds of gigabytes of third-party manuals, videos and encyclopedias, each under
  its own terms. It is distributed as packs, with a Sources and permissions page in each pack.
- **Models** (GGUF, ONNX): large, and published by their makers. Setup fetches them, and the checksums and pins are here.
- **Generated data** (`derived/`, builds, installers): everything there can be rebuilt with the scripts here.
- **Private data**: the household's own home area (`web/home-area.json`), the private word lists the scans use, machine
  and user names, keys and deploy settings. The guides here are already in their shipped, general wording. To keep your
  own home-area words out of a build, put them in a local copy of `packaging/ship_edits.json` (`forbidden`) and never
  commit it.

## Tests

```bash
python3 -B -m unittest app.tests.test_bridge app.tests.test_setup app.tests.test_data_folder app.tests.test_what_ships
```

These run without a library. `packaging/test_pack_tools.py SAMPLE WORK` checks the pack tools against a pack sample
(`build_packs.py build <pack> --sample N`). The `mac_*` and `win_*` scripts in `app/tests/` drive a real build against a real data
folder, and their paths are placeholders (`/path/to/lastbook`, `C:\Users\you\app-test`) to set for your own machine.

## Contributing and licence

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). The licence is still to be decided
([LICENSE](LICENSE)). Third-party software and models are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
