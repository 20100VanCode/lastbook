#!/usr/bin/env python3
"""Build every French département's pack, end to end, resumably.

  derived/buildenv/bin/python tools/build_all_fr.py \
      --cache derived/cache --out derived/packs --ign derived/geo/ign \
      [--only 971,972] [--force]

One département goes through six steps: BAN addresses, BD ALTI terrain, the OpenStreetMap
map, the BD TOPO names, the BD TOPO building heights, then the pack. Each step's output is
a file; a step whose file is already there is skipped, so an interrupted run continues
where it stopped. What was downloaded stays in --cache, so a second run costs no network.

Sources, per département:
  adresses  https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-<dep>.csv.gz
  terrain   IGN BD ALTI, the address from tools/ign_feed.py bdalti
  carte     Geofabrik, GeoPackage for France's regions and shapefiles for the DROM
  noms      IGN BD TOPO, the address from tools/ign_feed.py bdtopo
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from engine.departements import DEPARTEMENTS                            # noqa: E402

UA = {'User-Agent': 'relique-fr/1.0'}
BAN = 'https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-{}.csv.gz'
GEOFABRIK = 'https://download.geofabrik.de/europe/france/{}-latest-free.{}.zip'
# the département's region as Geofabrik names it (France's regions before 2016), and the DROM
REGION_OSM = {
    'alsace': 'alsace', 'aquitaine': 'aquitaine', 'auvergne': 'auvergne', 'basse_normandie': 'basse-normandie',
    'bourgogne': 'bourgogne', 'bretagne': 'bretagne', 'centre': 'centre', 'champagne_ardenne': 'champagne-ardenne',
    'corse': 'corse', 'franche_comte': 'franche-comte', 'haute_normandie': 'haute-normandie',
    'ile_de_france': 'ile-de-france', 'languedoc_roussillon': 'languedoc-roussillon', 'limousin': 'limousin',
    'lorraine': 'lorraine', 'midi_pyrenees': 'midi-pyrenees', 'nord_pas_de_calais': 'nord-pas-de-calais',
    'pays_de_la_loire': 'pays-de-la-loire', 'picardie': 'picardie', 'poitou_charentes': 'poitou-charentes',
    'provence_alpes_cote_d_azur': 'provence-alpes-cote-d-azur', 'rhone_alpes': 'rhone-alpes',
}
DROM_OSM = {'971': ('guadeloupe', 'shp'), '972': ('martinique', 'shp'), '973': ('guyane', 'shp'),
            '974': ('reunion', 'shp'), '976': ('mayotte', 'shp')}
# the region code IGN uses, for the départements the feed publishes only as a region
REGION_CODE = {
    '01': 'R84', '02': 'R32', '03': 'R84', '04': 'R93', '05': 'R93', '06': 'R93', '07': 'R84', '08': 'R44',
    '09': 'R76', '10': 'R44', '11': 'R76', '12': 'R76', '13': 'R93', '14': 'R28', '15': 'R84', '16': 'R75',
    '17': 'R75', '18': 'R24', '19': 'R75', '21': 'R27', '22': 'R53', '23': 'R75', '24': 'R75', '25': 'R27',
    '26': 'R84', '27': 'R28', '28': 'R24', '29': 'R53', '2A': 'R94', '2B': 'R94', '30': 'R76', '31': 'R76',
    '32': 'R76', '33': 'R75', '34': 'R76', '35': 'R53', '36': 'R24', '37': 'R24', '38': 'R84', '39': 'R27',
    '40': 'R75', '41': 'R24', '42': 'R84', '43': 'R84', '44': 'R52', '45': 'R24', '46': 'R76', '47': 'R75',
    '48': 'R76', '49': 'R52', '50': 'R28', '51': 'R44', '52': 'R44', '53': 'R52', '54': 'R44', '55': 'R44',
    '56': 'R53', '57': 'R44', '58': 'R27', '59': 'R32', '60': 'R32', '61': 'R28', '62': 'R32', '63': 'R84',
    '64': 'R75', '65': 'R76', '66': 'R76', '67': 'R44', '68': 'R44', '69': 'R84', '70': 'R27', '71': 'R27',
    '72': 'R52', '73': 'R84', '74': 'R84', '75': 'R11', '76': 'R28', '77': 'R11', '78': 'R11', '79': 'R75',
    '80': 'R32', '81': 'R76', '82': 'R76', '83': 'R93', '84': 'R93', '85': 'R52', '86': 'R75', '87': 'R75',
    '88': 'R44', '89': 'R27', '90': 'R27', '91': 'R11', '92': 'R11', '93': 'R11', '94': 'R11', '95': 'R11',
    '971': 'R01', '972': 'R02', '973': 'R03', '974': 'R04', '976': 'R06',
}
DEPARTEMENT_REGION_OLD = {
    '01': 'rhone_alpes', '02': 'picardie', '03': 'auvergne', '04': 'provence_alpes_cote_d_azur',
    '05': 'provence_alpes_cote_d_azur', '06': 'provence_alpes_cote_d_azur', '07': 'rhone_alpes',
    '08': 'champagne_ardenne', '09': 'midi_pyrenees', '10': 'champagne_ardenne', '11': 'languedoc_roussillon',
    '12': 'midi_pyrenees', '13': 'provence_alpes_cote_d_azur', '14': 'basse_normandie', '15': 'auvergne',
    '16': 'poitou_charentes', '17': 'poitou_charentes', '18': 'centre', '19': 'limousin', '2A': 'corse',
    '2B': 'corse', '21': 'bourgogne', '22': 'bretagne', '23': 'limousin', '24': 'aquitaine',
    '25': 'franche_comte', '26': 'rhone_alpes', '27': 'haute_normandie', '28': 'centre', '29': 'bretagne',
    '30': 'languedoc_roussillon', '31': 'midi_pyrenees', '32': 'midi_pyrenees', '33': 'aquitaine',
    '34': 'languedoc_roussillon', '35': 'bretagne', '36': 'centre', '37': 'centre', '38': 'rhone_alpes',
    '39': 'franche_comte', '40': 'aquitaine', '41': 'centre', '42': 'rhone_alpes', '43': 'auvergne',
    '44': 'pays_de_la_loire', '45': 'centre', '46': 'midi_pyrenees', '47': 'aquitaine', '48': 'languedoc_roussillon',
    '49': 'pays_de_la_loire', '50': 'basse_normandie', '51': 'champagne_ardenne', '52': 'champagne_ardenne',
    '53': 'pays_de_la_loire', '54': 'lorraine', '55': 'lorraine', '56': 'bretagne', '57': 'lorraine',
    '58': 'bourgogne', '59': 'nord_pas_de_calais', '60': 'picardie', '61': 'basse_normandie',
    '62': 'nord_pas_de_calais', '63': 'auvergne', '64': 'aquitaine', '65': 'midi_pyrenees',
    '66': 'languedoc_roussillon', '67': 'alsace', '68': 'alsace', '69': 'rhone_alpes', '70': 'franche_comte',
    '71': 'bourgogne', '72': 'pays_de_la_loire', '73': 'rhone_alpes', '74': 'rhone_alpes',
    '75': 'ile_de_france', '76': 'haute_normandie', '77': 'ile_de_france', '78': 'ile_de_france',
    '79': 'poitou_charentes', '80': 'picardie', '81': 'midi_pyrenees', '82': 'midi_pyrenees',
    '83': 'provence_alpes_cote_d_azur', '84': 'provence_alpes_cote_d_azur', '85': 'pays_de_la_loire',
    '86': 'poitou_charentes', '87': 'limousin', '88': 'lorraine', '89': 'bourgogne', '90': 'franche_comte',
    '91': 'ile_de_france', '92': 'ile_de_france', '93': 'ile_de_france', '94': 'ile_de_france',
    '95': 'ile_de_france',
}


def run(tool, *args):
    """Run one of the sibling build tools with this interpreter."""
    cmd = [sys.executable, '-B', str(HERE / 'tools' / tool)] + [str(a) for a in args]
    subprocess.run(cmd, check=True)


def head_size(url):
    try:
        head = urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers=UA), timeout=60)
        size = int(head.headers.get('Content-Length') or 0)
        head.close()
        return size
    except Exception:
        return 0


def fetch(url, path, tries=6):
    """Download to path, resuming a partial file and retrying what the server drops."""
    size = path.stat().st_size if path.exists() else 0
    remote = head_size(url)
    if size and (not remote or size >= remote):
        return path
    if size:
        print(f'  {path.name}: déjà là mais incomplet ({size:,} / {remote:,}), reprise', flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + '.part')
    for attempt in range(tries):
        have = part.stat().st_size if part.exists() else 0
        if remote and have > remote:
            part.unlink()
            have = 0
        headers = dict(UA)
        if have:
            headers['Range'] = f'bytes={have}-'
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=900) as src:
                if have and src.status != 206:
                    have = 0                      # the server ignored Range: start over
                with open(part, 'ab' if have else 'wb') as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        except Exception as exc:
            print(f'  {path.name}: essai {attempt + 1}/{tries} ({type(exc).__name__})', flush=True)
            time.sleep(min(60, 5 * (attempt + 1)))
            continue
        got = part.stat().st_size
        if not remote or got >= remote:
            part.replace(path)
            return path
        print(f'  {path.name}: {got:,} / {remote:,} octets, nouvel essai', flush=True)
        time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError(f'{path.name}: téléchargement incomplet après {tries} essais')


def unzip(path, into):
    """Extract a .zip or .7z into a fresh directory and return it."""
    shutil.rmtree(into, ignore_errors=True)
    into.mkdir(parents=True)
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as z:
            z.extractall(into)
    else:
        import py7zr
        with py7zr.SevenZipFile(path) as z:
            z.extractall(into)
    return into


def ban_bounds(path):
    """The département's own extent, recorded by build_addresses_fr.py — the map is cut to it."""
    if not path.is_file():
        return None
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        row = db.execute("SELECT value FROM meta WHERE key='bounds'").fetchone()
    finally:
        db.close()
    return row[0] if row and row[0] else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--out', required=True, help='where the packs go')
    ap.add_argument('--work', help='build folders; defaults to --out/.work')
    ap.add_argument('--ign', required=True, help='folder holding ign-bdtopo.json and ign-bdalti.json')
    ap.add_argument('--only', help='comma-separated département codes')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    cache, out = Path(a.cache), Path(a.out)
    work_root = Path(a.work) if a.work else out / '.work'
    ign = Path(a.ign)
    topo = json.loads((ign / 'ign-bdtopo.json').read_text(encoding='utf-8'))
    alti = json.loads((ign / 'ign-bdalti.json').read_text(encoding='utf-8'))
    regions = json.loads((ign / 'ign-bdtopo-regions.json').read_text(encoding='utf-8'))
    codes = [c.strip() for c in a.only.split(',')] if a.only else [d[0] for d in DEPARTEMENTS]
    unknown = [c for c in codes if c not in {d[0] for d in DEPARTEMENTS}]
    if unknown:
        raise SystemExit('départements inconnus : ' + ', '.join(unknown))

    done = []
    for code in codes:
        name = dict((d[0], d[1]) for d in DEPARTEMENTS)[code]
        work = work_root / f'FR-{code}'
        geo = work / 'derived' / 'geo'
        geo.mkdir(parents=True, exist_ok=True)
        print(f'\n=== {code} {name} ===', flush=True)
        try:
            # 1. adresses BAN
            target = geo / 'addresses' / f'FR-{code}.sqlite'
            if a.force or not target.exists():
                csv = fetch(BAN.format(code), cache / 'ban' / f'adresses-{code}.csv.gz')
                run('build_addresses_fr.py', '--csv', csv, '--departement', code, '--out', geo / 'addresses')
            # 2. terrain BD ALTI
            target = geo / 'terrain.sqlite'
            if a.force or not target.exists():
                entry = alti.get(code)
                if not entry:
                    raise RuntimeError('BD ALTI absente du flux')
                raw = unzip(fetch(entry['url'], cache / 'bdalti' / f'{code}.7z'), cache / 'bdalti' / code)
                grid = next(raw.rglob('*.asc'), None) or next(raw.rglob('*.asc.gz'), None)
                if not grid:
                    raise RuntimeError('pas de grille ASC dans la livraison')
                run('build_terrain_fr.py', '--dir', grid.parent, '--departement', code, '--out', target)
            # 3. carte OpenStreetMap
            target = geo / 'national.sqlite'
            made_map = a.force or not target.exists()
            if made_map:
                if code in DROM_OSM:
                    region, kind = DROM_OSM[code]
                else:
                    region, kind = REGION_OSM[DEPARTEMENT_REGION_OLD[code]], 'gpkg'
                raw = unzip(fetch(GEOFABRIK.format(region, kind), cache / 'osm' / f'{region}.{kind}.zip'),
                            cache / 'osm' / region)
                # a shapefile delivery is a directory of layers; a GeoPackage is one file
                source = raw if kind == 'shp' else next(raw.rglob('*.gpkg'), None)
                if not source:
                    raise RuntimeError(f'pas de .{kind} dans la livraison {region}')
                args = ['build_map_fr.py', f'--{kind}', source, '--departement', code, '--out', target]
                box = ban_bounds(geo / 'addresses' / f'FR-{code}.sqlite')
                if box:
                    # a box starts with a minus: argparse needs the = form to read it as a value
                    args += [f'--box={box}']
                run(*args)
            box = ban_bounds(geo / 'addresses' / f'FR-{code}.sqlite')
            if (geo / 'national.sqlite').exists():
                status = {'country': 'FR', 'departement': code, 'state': 'built',
                          'source': '© OpenStreetMap contributors, via Geofabrik (ODbL 1.0)',
                          'bounds': box or '', 'built': time.strftime('%Y-%m-%dT%H:%M:%S')}
                (geo / 'national-status.json').write_text(json.dumps(status), encoding='utf-8')
                (geo / 'socal-cells.json').write_text('[]', encoding='utf-8')
            # 4. noms BD TOPO, puis 5. hauteurs de bâtiments
            entry = topo.get(code)
            box = ban_bounds(geo / 'addresses' / f'FR-{code}.sqlite')
            box_args = [f'--box={box}'] if box else []
            if not entry:
                # a handful of départements are published only inside their region's file
                entry = regions.get(REGION_CODE[code])
                if not entry:
                    raise RuntimeError('BD TOPO absente du flux, département et région')
                if not box:
                    raise RuntimeError('BD TOPO régionale sans boîte BAN : impossible de découper')
                print('  édition régionale, découpée à la boîte BAN', flush=True)
            raw = unzip(fetch(entry['url'], cache / 'bdtopo' / f'{code}.7z'), cache / 'bdtopo' / code)
            target = geo / 'buildings.sqlite'
            if made_map:
                run('build_topo_fr.py', '--dir', raw, '--departement', code, '--map', geo / 'national.sqlite', *box_args)
            if a.force or not target.exists():
                run('build_bldg_fr.py', '--dir', raw, '--departement', code, '--out', target, *box_args)
            # 6. le pack
            run('build_pack_fr.py', '--data', work, '--departement', code, '--out', out / f'FR-{code}')
            done.append(code)
            print(f'  → pack {code} prêt', flush=True)
        except Exception as exc:
            print(f'  ÉCHEC {code} : {type(exc).__name__}: {exc}', flush=True)
    print(f'\n{done and len(done)}/{len(codes)} départements : {", ".join(done)}', flush=True)


if __name__ == '__main__':
    main()
