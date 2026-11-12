"""Food stores from USDA's SNAP retailer list: derived/geo/places-snap.sqlite.

  derived/buildenv/bin/python tools/build_places_snap.py

Every store authorized to take SNAP benefits (supermarkets, grocers, corner stores, farmers' markets), with
coordinates, from https://www.fns.usda.gov/snap/retailer-locator/data (public domain). Keeps stores still authorized
(no end date). Store numbers are cut from the names ('Aldi 019' -> 'Aldi') and drugstore chains filed as
'Combination Grocery/Other' become pharmacies. Same table as tools/build_places_overture.py so game/serve.py can merge them.

The CSV comes from the zip on that page (it is not downloaded here): unzip it into derived/geo/sources/snap/.
"""
import re, sqlite3, sys, time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'derived/geo/sources/snap/Historical SNAP Retailer Locator Data 2005-2025.csv'
OUT = HERE / 'derived/geo/places-snap.sqlite'
CLASSES = {'Supermarket': 'supermarket', 'Super Store': 'supermarket', 'Large Grocery Store': 'supermarket',
           'Medium Grocery Store': 'supermarket', 'Military Commissary': 'supermarket', 'Food Buying Co-op': 'supermarket',
           'Small Grocery Store': 'convenience', 'Combination Grocery/Other': 'convenience', 'Convenience Store': 'convenience',
           "Farmers' Market": 'marketplace', 'Meat/Poultry Specialty': 'butcher', 'Bakery Specialty': 'bakery',
           'Seafood Specialty': 'seafood', 'Fruits/Veg Specialty': 'greengrocer'}


DRUG = re.compile(r'\bcvs\b|walgreens|duane reade|\bpharmacy\b|\bdrugs?\b', re.I)


def tidy(n):
    """game/serve.py's tidy_name: 'ALDI 019' -> 'Aldi', '7-Eleven 42695H' -> '7-Eleven', "Zabar'S & Co" -> "Zabar's"."""
    n = ' '.join(n.split())
    n = re.sub(r'(\s+(#\s*)?[A-Za-z]{0,3}-?\d+[A-Za-z]?)+$', '', n).strip(' -#,|')
    if n.isupper() or n.islower():
        n = n.title()
    n = re.sub(r"'S\b", "'s", n)
    n = re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda m: m[1] + m[2].lower(), n)
    return re.sub(r',?\s+(&\s*)?(Inc|Llc|Co|Corp)\.?$', '', n, flags=re.I).strip(' ,|')


def cell(v):
    return int(v * 20) if v >= 0 else int(v * 20) - 1


def main():
    if not SRC.exists():
        sys.exit(f'missing {SRC}: download the zip from https://www.fns.usda.gov/snap/retailer-locator/data and unzip it there')
    rows = duckdb.sql(f"""SELECT "Store Type", trim("Store Name"), "Latitude", "Longitude"
        FROM read_csv_auto('{SRC}', all_varchar=false) WHERE trim(coalesce(CAST("End Date" AS VARCHAR), '')) = ''
          AND "Latitude" IS NOT NULL AND "Latitude" <> 0""").fetchall()
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    out = []
    for t, n, la, lo in rows:
        if t not in CLASSES or not n:
            continue
        cls, n = CLASSES[t], tidy(n.title())
        if re.search(r'rite aid', n, re.I):
            continue  # Rite Aid closed all its stores in 2025
        if cls == 'convenience' and DRUG.search(n):
            cls = 'pharmacy'
        if len(n) > 1:
            out.append((cls, n, la, lo, cell(lo), cell(la)))
    db.executemany('INSERT INTO place VALUES (?,?,?,?,1,?,?)', out)
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    n = db.execute('SELECT count(*) FROM place').fetchone()[0]
    db.executemany('INSERT INTO meta VALUES (?,?)', [('count', str(n)), ('source', 'USDA FNS SNAP retailer locator, data to 2025'),
                                                    ('licence', 'Public domain (US federal government work, USDA FNS)'),
                                                    ('built', time.strftime('%Y-%m-%dT%H:%M:%S'))])
    db.commit(); db.close()
    tmp.replace(OUT)
    print(f'{n:,} stores')


if __name__ == '__main__':
    main()
