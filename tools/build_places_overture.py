"""Places the game needs, from Overture Maps: derived/geo/places-overture.sqlite.

  derived/buildenv/bin/python tools/build_places_overture.py [--release 2026-10-21.0]

OpenStreetMap's shops and services are well mapped in big cities but thin in many suburbs and small towns (around Novi,
Michigan it has one supermarket and no hardware store within 5 km). Overture's places theme (built from Meta and
Microsoft listings among others, CDLA-Permissive-2.0) covers them far better. Keeps US places of the kinds the game
uses, open (or status unknown) and with confidence above 0.5, mapped to the game's OpenStreetMap-style classes so
game/serve.py can merge both sources. Streams from Overture's public S3 bucket with DuckDB. Clinics named after a
person ('Jane Doe, MD', 'Dr. Smith') are left out: they are individual doctors, often at home offices.

Licence: CDLA-Permissive-2.0 (https://cdla.dev/permissive-2-0/), stored in meta 'licence'. Anything that ships this
file, or places from it, must carry the licence text and the attribution "© Overture Maps Foundation" (and, for the
places theme, its upstream credits listed at https://docs.overturemaps.org/attribution/).
"""
import argparse, re, sqlite3, time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/places-overture.sqlite'
# Overture taxonomy -> the game's class (OpenStreetMap names, as /api/map/near returns them)
CLASSES = {
    'supermarket': 'supermarket', 'grocery_store': 'supermarket', 'warehouse_club': 'supermarket', 'wholesale_store': 'supermarket',
    'international_grocery_store': 'supermarket', 'indian_grocery_store': 'supermarket', 'asian_grocery_store': 'supermarket',
    'mexican_grocery_store': 'supermarket', 'health_food_store': 'supermarket', 'organic_grocery_store': 'supermarket',
    'convenience_store': 'convenience',
    'hardware_store': 'hardware', 'home_improvement_store': 'hardware', 'building_supply_store': 'hardware', 'lumber_store': 'hardware',
    'gas_station': 'fuel',
    'pharmacy': 'pharmacy', 'drugstore': 'pharmacy',
    'urgent_care_clinic': 'clinic', 'medical_center': 'clinic', 'community_health_center': 'clinic', 'walk_in_clinic': 'clinic',
    'hospital': 'hospital', 'emergency_department': 'hospital', 'childrens_hospital': 'hospital',
    'fire_station': 'fire_station', 'police_station': 'police',
    'community_center': 'community_centre', 'library': 'library',
}


# a doctor's own listing: 'Joshua Minuto, MD', 'Dr. Edmund Liu', 'Michelle B Cung, DO' (also used by build_places_fsq.py)
DOCTOR = re.compile(r"^(dr|dra|drs|doctor)(\.|'s\b|\s|$)|[,\s](md|m\.d|do|d\.o|np|fnp|fnp-c|pa-c|dpm|dds|dmd|od|phd|psyd|lcsw|aprn|crnp|rn|facp|faafp|faap|mph|msn|dnp|mpas)\.?"
                    r"\s*(,|$|-|\(|\||pc\b|pa\b|p\.c\.|office|ms\b|vip)|^[A-Z][a-z'-]+, [A-Z][a-z'-]+$", re.I)
PERSON = re.compile(r"^[A-Z][a-z'-]+( [A-Z]\.?)?( [A-Z][a-z'-]+){1,2}$")  # 'Jane Doe', 'Jane A Doe'
PRACTICE = re.compile(r'clinic|health|medic|care|cent(er|re)|family|pediatric|practice|associates|group|physicians|doctors|urgent|'
                      r'wellness|hospital|partners|primary|internal|community', re.I)


def doctor_named(name):
    return bool(DOCTOR.search(name) or (PERSON.match(name) and not PRACTICE.search(name)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', default='2026-10-21.0')
    a = ap.parse_args()
    t0 = time.time()
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    cats = ','.join(f"'{k}'" for k in CLASSES)
    cur = c.execute(f"""
        SELECT taxonomy.primary, names.primary, round(ST_Y(geometry), 6), round(ST_X(geometry), 6), round(confidence, 2)
        FROM read_parquet('s3://overturemaps-us-west-2/release/{a.release}/theme=places/type=place/*', hive_partitioning=1)
        WHERE taxonomy.primary IN ({cats}) AND confidence > 0.5 AND coalesce(operating_status, 'open') = 'open'
          AND addresses[1].country = 'US' AND names.primary IS NOT NULL""")
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    total = 0
    while rows := cur.fetchmany(200_000):
        rows = [r for r in rows if not (CLASSES[r[0]] in ('clinic', 'hospital') and doctor_named(r[1]))]
        db.executemany('INSERT INTO place VALUES (?,?,?,?,?,?,?)',
                       ((CLASSES[k], n, la, lo, cf, int(lo * 20) if lo >= 0 else int(lo * 20) - 1, int(la * 20) if la >= 0 else int(la * 20) - 1)
                        for k, n, la, lo, cf in rows))  # grid of 0.05 degrees for nearby lookups
        total += len(rows)
        print(f'{total:,} places, {time.time() - t0:.0f}s', flush=True)
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [('count', str(total)), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
                                                    ('source', f'Overture Maps places {a.release}'),
                                                    ('licence', 'CDLA-Permissive-2.0 (https://cdla.dev/permissive-2-0/); '
                                                                'attribution: © Overture Maps Foundation, see https://docs.overturemaps.org/attribution/')])
    db.commit(); db.close()
    tmp.replace(OUT)
    print(f'done: {total:,} places in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
