"""Street addresses for address search, France: derived/geo/addresses/FR-<dep>.sqlite,
from the Base Adresse Nationale (BAN).

  python3 tools/build_addresses_fr.py --departement 972 [--csv adresses-972.csv.gz]

Reads the BAN's daily département CSV (id;numero;rep;nom_voie;code_postal;code_insee;
nom_commune;…), keeps one département, folds the street name exactly as
engine/address_search.py does, and writes the same addr table as the US builder, with
meta.country='FR' so the engine searches it with French rules. The WGS84 longitude and
latitude columns are used as they are: no projection conversion is needed.

Licence Ouverte 2.0 (Etalab). The source is the BAN's own daily file, not a mirror.
"""
import argparse
import csv
import gzip
import sqlite3
import string
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from engine.address_search import normalize_fr  # noqa: E402

URL = 'https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-{dep}.csv.gz'
# The BAN's repetition field is "bis", "ter", "quater" or a single letter (a…z).
# A number there is a floor or door, not a repetition, and is left out.
REPETITION = {'bis', 'ter', 'quater', 'quatr'} | set(string.ascii_lowercase)


def departement_of(code_insee):
    """The département from a commune code: 971-976 are three digits, Corsica 2A/2B, else two."""
    code = (code_insee or '').strip()
    if code[:3] in ('971', '972', '973', '974', '975', '976'):
        return code[:3]
    return code[:2]


def fetch(dep, path):
    print(f'downloading {URL.format(dep=dep)}', flush=True)
    urllib.request.urlretrieve(URL.format(dep=dep), path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--departement', required=True, help='14, 2A, 972…')
    ap.add_argument('--csv', help='a downloaded adresses-<dep>.csv.gz; downloaded if omitted')
    ap.add_argument('--out', default=str(HERE / 'derived' / 'geo' / 'addresses'))
    a = ap.parse_args()

    src = Path(a.csv) if a.csv else HERE / 'derived' / 'geo' / f'adresses-{a.departement}.csv.gz'
    if not src.is_file():
        fetch(a.departement, src)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / f'FR-{a.departement}.partial.sqlite'
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA page_size=8192; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; '
                     'PRAGMA cache_size=-1024; PRAGMA temp_store=FILE; '
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL); '
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    opener = gzip.open if src.suffix == '.gz' else open
    total = kept = 0
    skipped = 0
    started = time.time()
    batch = []
    with opener(src, 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter=';'):
            total += 1
            if departement_of(row.get('code_insee')) != a.departement:
                continue
            numero = (row.get('numero') or '').strip()
            street = (row.get('nom_voie') or '').strip()
            if not numero or not street:
                continue
            rep = (row.get('rep') or '').strip().lower()
            if rep and rep not in REPETITION:
                skipped += 1          # a floor or door number in the repetition field
                continue
            try:
                lat = float(row['lat'])
                lon = float(row['lon'])
            except (KeyError, ValueError):
                continue
            batch.append((f'{numero} {rep}'.strip(), street, normalize_fr(street),
                          (row.get('nom_commune') or '').strip(), a.departement,
                          (row.get('code_postal') or '').strip(), lat, lon))
            kept += 1
            if len(batch) >= 50_000:
                db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
                batch.clear()
                print(f'{kept:,} kept of {total:,}, {time.time() - started:.0f}s', flush=True)
    if batch:
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
    print('indexing', flush=True)
    db.executescript('CREATE INDEX addr_norm ON addr(norm,num); CREATE INDEX addr_num_norm ON addr(num,norm);')
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('country', 'FR'), ('departement', a.departement), ('count', str(kept)),
        ('norm', 'fr-1'), ('skipped_repetition', str(skipped)),
        ('source', 'Base Adresse Nationale (BAN), fichier départemental quotidien'),
        ('source_built', time.strftime('%Y-%m-%dT%H:%M:%S')),
        ('licence', 'Licence Ouverte 2.0 (Etalab)'),
    ])
    db.commit()
    check = db.execute('PRAGMA quick_check').fetchone()[0]
    if check != 'ok':
        raise RuntimeError(f'FR-{a.departement}: SQLite check failed: {check}')
    db.close()
    final = out / f'FR-{a.departement}.sqlite'
    tmp.replace(final)
    print(f'done: {kept:,} addresses ({skipped:,} skipped) in {time.time() - started:.0f}s -> {final}', flush=True)


if __name__ == '__main__':
    main()
