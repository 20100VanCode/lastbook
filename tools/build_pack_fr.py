#!/usr/bin/env python3
"""Assemble a RELIQUE map pack and an address-index pack for one French département.

  derived/buildenv/bin/python tools/build_pack_fr.py \
      --data derived/geo --departement 972 --out derived/packs/fr-972

A map pack is what setup installs (docs/SETUP-API.md, State maps): a zip holding only
map-set.json, derived/geo/*.sqlite, derived/geo/national-status.json and
derived/geo/socal-cells.json, where map-set.json names the set and the files with their
sizes. The address index is a second zip holding one file,
derived/geo/addresses/<id>.sqlite.

Both are verified the way setup verifies them (install.check_zip with install.map_member,
then install.check_map on the unpacked set), so a pack that builds here installs there.
A manifest fragment is written beside them, ready to serve from a download site.
"""
import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from engine.setup import install                                    # noqa: E402

SQLITE_SIDES = ('', '-wal', '-shm', '-journal')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write_zip(path, members):
    """members: list of (relative name, source path). Stored, not deflated: the app reads them as a stream."""
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, src in members:
            z.write(src, rel)
            total += Path(src).stat().st_size
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='a data folder holding derived/geo/')
    ap.add_argument('--departement', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default=None)
    ap.add_argument('--includes', default='Rues, bâtiments, eau, lieux-dits et relief, plus les adresses de la BAN')
    a = ap.parse_args()
    geo = Path(a.data) / 'derived' / 'geo'
    pack_id = 'FR-' + a.departement
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    national = geo / 'national.sqlite'
    terrain = geo / 'terrain.sqlite'
    status = geo / 'national-status.json'
    socal = geo / 'socal-cells.json'
    buildings = geo / 'buildings.sqlite'
    missing = [p.name for p in (national, terrain, status) if not p.is_file()]
    if missing:
        raise SystemExit('manquant dans ' + str(geo) + ' : ' + ', '.join(missing))

    # --- the map set, on disk as setup will see it after unpacking -------------
    members = [('derived/geo/' + p.name, p) for p in (status, national, terrain, socal, buildings) if p.is_file()]
    installed = sum(p.stat().st_size for _, p in members)
    set_json = {'name': pack_id, 'files': {rel: src.stat().st_size for rel, src in members}}

    map_zip = out / f'Lastbook-Map-{pack_id}.zip'
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'map-set.json').write_text(json.dumps(set_json, indent=1), encoding='utf-8')
        write_zip(map_zip, [('map-set.json', tmp / 'map-set.json')] + members)

        # --- the address index -------------------------------------------------
        addr = geo / 'addresses' / (pack_id + '.sqlite')
        addr_zip = out / f'Lastbook-Addresses-{pack_id}.zip'
        if addr.is_file():
            write_zip(addr_zip, [('derived/geo/addresses/' + addr.name, addr)])
        elif (geo / 'addresses').is_dir():
            print(f'  aucune adresse pour {pack_id} dans {geo / "addresses"}')

        # --- verify exactly as setup does -------------------------------------
        install.check_zip(map_zip, installed, install.map_member)
        noop = type('Control', (), {'check': lambda self: None})()
        with tempfile.TemporaryDirectory() as ut:
            lib = install.unpack(map_zip, ut, installed, noop, lambda done, total: None, allowed=install.map_member)
            install.check_map(lib)
            if install.map_name(lib) != pack_id:
                raise SystemExit(f'map-set.json nomme {install.map_name(lib)}, pas {pack_id}')
            print(f'  carte vérifiée : {install.map_name(lib)}, {len(install.map_files(lib))} fichiers, {installed / 1e6:.1f} Mo')
        if addr_zip.is_file():
            dirs = {'', 'derived', 'derived/geo', 'derived/geo/addresses'}
            rel = 'derived/geo/addresses/' + addr.name
            install.check_zip(addr_zip, addr.stat().st_size,
                              lambda name, is_dir=False: name in dirs if is_dir else name == rel)
            print(f'  adresses vérifiées : {rel}, {addr.stat().st_size / 1e6:.1f} Mo')

    entries = {'maps': [{'id': pack_id, 'title': a.title or f'Département {a.departement}',
                         'kind': 'state', 'installed_bytes': installed, 'available': True,
                         'includes': a.includes,
                         'files': [{'name': map_zip.name, 'url': f'https://downloads.lastbook.org/maps/{map_zip.name}',
                                    'size': map_zip.stat().st_size, 'sha256': sha256(map_zip), 'kind': 'zip'}]}]}
    if addr_zip.is_file():
        entries['address_indexes'] = [{'id': pack_id, 'title': a.title or f'Département {a.departement}',
                                       'kind': 'state', 'includes': 'Adresses de la BAN',
                                       'installed_bytes': addr.stat().st_size, 'available': True,
                                       'files': [{'name': addr_zip.name, 'url': f'https://downloads.lastbook.org/addresses/{addr_zip.name}',
                                                  'size': addr_zip.stat().st_size, 'sha256': sha256(addr_zip), 'kind': 'zip'}]}]
    (out / 'manifest-fragment.json').write_text(json.dumps(entries, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'→ {map_zip} ({map_zip.stat().st_size / 1e6:.1f} Mo)')
    if addr_zip.is_file():
        print(f'→ {addr_zip} ({addr_zip.stat().st_size / 1e6:.1f} Mo)')
    print(f'→ {out / "manifest-fragment.json"}')


if __name__ == '__main__':
    main()
