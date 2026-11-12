"""Builds derived/geo/buildings.sqlite: Microsoft building footprints for the US, bucketed by zoom-14 tile.

  derived/buildenv/bin/python tools/build_buildings.py [--workers N] [--socal]

Source: Microsoft Global ML Building Footprints (ODbL), fetched by tools/fetch_msbuildings.sh into
derived/geo/sources/msbuildings/<Region>/<quadkey>.csv.gz (one GeoJSON feature per line).
Table bldg(x, y, part, n, data): x/y = z14 tile holding the building's centre, part = source file number.
data = zlib(int32 array): per building [npts, height_dm, X0, Y0, dX1, dY1, ...] where X/Y are global
z14 pixel coordinates scaled by 65536 (i.e. web-mercator in units of 2^-30 of the world), first point
absolute and the rest as deltas. Buildings in Southern California cells where OpenStreetMap already has most
of the buildings (derived/geo/socal-bldg-cells.json, from tools/socal_bldg_cells.py) are skipped; --socal puts
just those into table bldg_socal instead, which only the 3D view reads (OSM's SoCal outlines carry no heights).
A footprint reaching more than ~150 m into a neighbouring z14 bucket is stored in that bucket too.
"""
import argparse, gzip, json, math, os, sqlite3, sys, time, zlib
from array import array
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'derived/geo/sources/msbuildings'
OUT = Path(os.environ.get('BUILDINGS_OUT', HERE / 'derived/geo/buildings.sqlite'))
SKIP_CELLS = HERE / 'derived/geo/socal-bldg-cells.json'
REACH = 1 << 12  # server and 3D view look this far (~150 m) into neighbouring buckets; bigger footprints are filed in each bucket they overlap
SOCAL_CELL = 0.05
WORLD = 2 ** 30
SOCAL = set()


def init():
    global SOCAL
    try:
        SOCAL = set(json.loads(SKIP_CELLS.read_text()))
    except (OSError, ValueError):
        SOCAL = set()


def convert(args):
    part, path, socal_only = args
    tiles, n, skipped = {}, 0, 0
    with gzip.open(path, 'rt') as f:
        for line in f:
            try:
                ft = json.loads(line)
                g = ft['geometry']
                ring = g['coordinates'][0] if g['type'] == 'Polygon' else g['coordinates'][0][0]
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) < 3:
                continue
            clon = sum(p[0] for p in ring) / len(ring)
            clat = sum(p[1] for p in ring) / len(ring)
            if (int((clon + 180) / SOCAL_CELL) * 100000 + int((clat + 90) / SOCAL_CELL) in SOCAL) != socal_only:
                skipped += 1
                continue
            pts = []
            for lon, lat in ring:
                s = math.sin(math.radians(max(-85, min(85, lat))))
                pts.append((int((lon + 180) / 360 * WORLD), int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * WORLD)))
            cx = sum(p[0] for p in pts) // len(pts); cy = sum(p[1] for p in pts) // len(pts)
            h = (ft.get('properties') or {}).get('height', -1)
            h = int(round(h * 10)) if isinstance(h, (int, float)) and h > 0 else 0
            rec = array('i', (len(pts), h, pts[0][0], pts[0][1]))
            lx, ly = pts[0]
            for x, y in pts[1:]:
                rec.extend((x - lx, y - ly)); lx, ly = x, y
            bx, by = cx >> 16, cy >> 16
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            keys = {(i, j) for i in range((min(xs) + REACH) >> 16, ((max(xs) - REACH) >> 16) + 1)
                    for j in range((min(ys) + REACH) >> 16, ((max(ys) - REACH) >> 16) + 1)} | {(bx, by)}
            for key in keys:  # readers drop the copies of a big footprint by its first point
                a = tiles.get(key)
                if a is None:
                    a = tiles[key] = [array('i'), 0]
                a[0].extend(rec); a[1] += 1
            n += 1
    rows = [(x, y, part, c, zlib.compress(buf.tobytes(), 6)) for (x, y), (buf, c) in tiles.items()]
    return rows, n, skipped, str(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--socal', action='store_true', help='only the SoCal buildings, into bldg_socal (for 3D)')
    a = ap.parse_args()
    if not SKIP_CELLS.exists():
        sys.exit(f'{SKIP_CELLS} missing: run tools/socal_bldg_cells.py first')
    table, donet = ('bldg_socal', 'done_socal') if a.socal else ('bldg', 'done')
    files = sorted(SRC.glob('*/*.csv.gz'))
    db = sqlite3.connect(OUT)
    db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
                     'CREATE TABLE IF NOT EXISTS bldg(x INT, y INT, part INT, n INT, data BLOB, PRIMARY KEY(x,y,part)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS done(file TEXT PRIMARY KEY, n INT);'
                     'CREATE TABLE IF NOT EXISTS bldg_socal(x INT, y INT, part INT, n INT, data BLOB, PRIMARY KEY(x,y,part)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS done_socal(file TEXT PRIMARY KEY, n INT);'
                     'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);')
    finished = {r[0] for r in db.execute(f'SELECT file FROM {donet}')}
    todo = [(i, p, a.socal) for i, p in enumerate(files) if str(p) not in finished]
    print(f'{len(files)} files, {len(finished)} already converted, {len(todo)} to go', flush=True)
    t0, total, skipped, k = time.time(), 0, 0, 0
    with ProcessPoolExecutor(a.workers, initializer=init) as pool:
        for fut in as_completed([pool.submit(convert, j) for j in todo]):
            rows, n, s, path = fut.result()
            db.executemany(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?)', rows)
            db.execute(f'INSERT OR REPLACE INTO {donet} VALUES (?,?)', (path, n))
            total += n; skipped += s; k += 1
            if k % 50 == 0:
                db.commit()
                print(f'{k}/{len(todo)} files, {total:,} buildings ({skipped:,} skipped), {time.time() - t0:.0f}s', flush=True)
    if a.socal:
        db.commit()
        print(f'done: {total:,} SoCal buildings for 3D in {time.time() - t0:.0f}s', flush=True)
        return
    total_all = db.execute('SELECT sum(n) FROM done').fetchone()[0] or 0
    db.execute("INSERT OR REPLACE INTO meta VALUES ('buildings', ?)", (str(total_all),))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('source', 'Microsoft Global ML Building Footprints, release 2026-02-03 (ODbL)')",)
    db.commit()
    print(f'done: {total_all:,} buildings in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
