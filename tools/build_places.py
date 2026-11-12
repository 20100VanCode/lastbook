#!/usr/bin/env python3
"""Build the offline place finder (derived/geo/places.sqlite) from data already in the library:
USGS GNIS populated places, Census 2025 ZIP-code (ZCTA) and county gazetteers, and named OpenStreetMap
places/points from derived/geo/map.sqlite. Source zips are read, never modified.

  python3 tools/build_places.py
"""
import csv, io, sqlite3, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
LIB = HERE / 'library-data' / 'geography'
OUT = HERE / 'derived' / 'geo' / 'places.sqlite'
STATES = {}


def rows(zpath, member_suffix):
    with zipfile.ZipFile(zpath) as z:
        name = next(n for n in z.namelist() if n.endswith(member_suffix))
        with z.open(name) as f:
            text = io.TextIOWrapper(f, encoding='utf-8-sig', errors='replace')
            yield from csv.DictReader(text, delimiter='|')


def main():
    OUT.unlink(missing_ok=True)
    db = sqlite3.connect(OUT)
    db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
      CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
    ins = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
    n = 0
    for r in rows(LIB / 'geographic-names/PopulatedPlaces_National_Text.zip', 'PopulatedPlaces_National.txt'):
        try:
            lat, lon = float(r['prim_lat_dec']), float(r['prim_long_dec'])
        except ValueError:
            continue
        if not lat:
            continue
        db.execute(ins, (r['feature_name'], 'town or neighborhood', f"{r['county_name']} County, {r['state_name']}", lat, lon, 3, 'USGS GNIS'))
        n += 1
    for r in rows(LIB / 'census-gazetteers/2025_Gaz_zcta_national.zip', '.txt'):
        r = {k.strip(): v for k, v in r.items()}
        db.execute(ins, (r['GEOID'], 'ZIP code area', 'Census 2025 ZIP code tabulation area', float(r['INTPTLAT']), float(r['INTPTLONG'].strip()), 2, 'US Census Bureau'))
        n += 1
    for r in rows(LIB / 'census-gazetteers/2025_Gaz_counties_national.zip', '.txt'):
        r = {k.strip(): v for k, v in r.items()}
        db.execute(ins, (r['NAME'], 'county', r['USPS'], float(r['INTPTLAT']), float(r['INTPTLONG'].strip()), 2, 'US Census Bureau'))
        n += 1
    m = HERE / 'derived/geo/map.sqlite'
    if m.exists():
        src = sqlite3.connect(f'file:{m}?mode=ro', uri=True)
        for cls, name, lon, lat in src.execute("SELECT cls,name,lon,lat FROM poi WHERE name IS NOT NULL AND name<>''"):
            db.execute(ins, (name, cls.replace('_', ' '), 'Southern California (OpenStreetMap)', lat, lon, 4, 'OpenStreetMap'))
            n += 1
        import struct
        for cls, name, g in src.execute("SELECT cls,name,geom FROM feat WHERE layer='place' AND name IS NOT NULL"):
            _, _, x, y = struct.unpack_from('<iiii', g)
            db.execute(ins, (name, cls, 'Southern California (OpenStreetMap)', y / 1e6, x / 1e6, 1, 'OpenStreetMap'))
            n += 1
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    db.commit()
    print('places', n)


main()
