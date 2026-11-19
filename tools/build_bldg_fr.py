#!/usr/bin/env python3
"""3D building footprints with their measured height, from BD TOPO (IGN, Licence Ouverte 2.0).

  derived/buildenv/bin/python tools/build_bldg_fr.py \
      --dir derived/geo/bdtopo-972 --departement 972 --out derived/geo/buildings.sqlite

The 3D view (web/terrain3d.js) reads /api/map/bldg3d/<x14>/<y14>, which serves the
buildings.sqlite this writes: table bldg_osm, the same records as
tools/build_osm_heights.py — [npts, height_dm, min_height_dm, is_part, X0, Y0, dX1,
dY1, ...] in 2^-30 world units, bucketed by zoom-14 tile, zlib-compressed.

BD TOPO measures the height of nearly every building, so the 3D view shows real roofs
instead of satellite estimates. Buildings without a usable height are left out: the 2D
map still draws their footprint.
"""
import argparse
import math
import sqlite3
import time
import zlib
from array import array
from pathlib import Path

from pyproj import CRS


def delivery(src):
    """(kind, target, epsg): IGN's 3.5 is a GeoPackage inside the 7z, 3.0 and older are shapefiles."""
    gpkg = next(iter(sorted(src.rglob('*.gpkg'))), None)
    if gpkg:
        db = sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True)
        try:
            row = db.execute('SELECT srs_id FROM gpkg_contents LIMIT 1').fetchone()
        finally:
            db.close()
        return 'gpkg', gpkg, int(row[0]) if row else 4326
    prj = next(iter(sorted(p for p in src.rglob('*.prj') if not p.name.startswith('._'))), None)
    if prj is None:
        raise SystemExit('ni .gpkg ni .prj dans la livraison BD TOPO')
    # IGN écrit ses .prj en Latin-1 : on décode en tolérant.
    text = prj.read_bytes().decode('utf-8', errors='replace')
    return 'shp', src, CRS.from_wkt(text).to_epsg() or 4326

WORLD = 2 ** 30
STOREY = 3.2


def xy(lon, lat):
    s = math.sin(math.radians(max(-85.0, min(85.0, lat))))
    return (int((lon + 180) / 360 * WORLD), int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * WORLD))


def wkb_parts(b, o=0):
    """(list of flat [x,y,...] rings, offset); the type is read modulo 1000 for Z/M flags."""
    import struct
    le = b[o] == 1
    e = '<' if le else '>'
    t = struct.unpack_from(e + 'I', b, o + 1)[0] % 1000
    o += 5
    if t == 1:
        return [[struct.unpack_from(e + 'dd', b, o)[0], struct.unpack_from(e + 'dd', b, o + 8)[0]]], o + 16
    if t == 2:
        n = struct.unpack_from(e + 'I', b, o)[0]
        return [list(struct.unpack_from(e + '%dd' % (2 * n), b, o + 4))], o + 4 + 16 * n
    if t == 3:
        nr = struct.unpack_from(e + 'I', b, o)[0]
        o += 4
        parts = []
        for _ in range(nr):
            n = struct.unpack_from(e + 'I', b, o)[0]
            parts.append(list(struct.unpack_from(e + '%dd' % (2 * n), b, o + 4)))
            o += 4 + 16 * n
        return parts, o
    if t in (4, 5, 6, 7):
        n = struct.unpack_from(e + 'I', b, o)[0]
        o += 4
        parts = []
        for _ in range(n):
            p, o = wkb_parts(b, o)
            parts.extend(p)
        return parts, o
    raise ValueError('geometry type %d' % t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='unzipped BD TOPO 7z directory')
    ap.add_argument('--departement', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--min', type=float, default=2.0, help='a building shorter than this is not a building')
    ap.add_argument('--max', type=float, default=560.0)
    ap.add_argument('--box', help='W,S,E,N — limiter à un département quand la livraison est régionale')
    a = ap.parse_args()
    only = tuple(float(v) for v in a.box.split(',')) if a.box else None
    src = Path(a.dir)
    kind, target, epsg = delivery(src)
    print(f'CRS EPSG:{epsg}, livraison {"GeoPackage" if kind == "gpkg" else "shapefiles"}', flush=True)

    import duckdb
    con = duckdb.connect()
    con.execute('INSTALL spatial; LOAD spatial;')
    con.execute('SET geometry_always_xy = true')
    layer = 'batiment' if kind == 'gpkg' else str(next(iter(sorted(src.rglob('BATI/BATIMENT.shp')))))
    geom = 'geometrie' if kind == 'gpkg' else 'geom'
    if kind == 'gpkg':
        describe, args = 'DESCRIBE SELECT * FROM ST_Read(?, layer=?)', [str(target), layer]
    else:
        describe, args = 'DESCRIBE SELECT * FROM ST_Read(?)', [layer]
    have = {r[0].lower(): r[0] for r in con.execute(describe, args).fetchall()}
    if 'hauteur' not in have:
        raise SystemExit('la couche batiment n’a pas de colonne hauteur')
    select = f"ST_AsWKB(ST_Force2D(ST_Transform({geom}, 'EPSG:{epsg}', 'EPSG:4326'))), {have['hauteur']}"
    if kind == 'gpkg':
        sql, args = f'SELECT {select} FROM ST_Read(?, layer=?) WHERE {have["hauteur"]} IS NOT NULL', [str(target), layer]
    else:
        sql, args = f'SELECT {select} FROM ST_Read(?) WHERE {have["hauteur"]} IS NOT NULL', [layer]
    rows = con.execute(sql, args).fetchall()

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.partial')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE bldg_osm(x INT, y INT, n INT, data BLOB, PRIMARY KEY(x,y)) WITHOUT ROWID;'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    tiles, kept, skipped = {}, 0, 0
    t0 = time.time()
    for wkb, height in rows:
        h = float(height or 0)
        if not (a.min <= h <= a.max):
            skipped += 1
            continue
        try:
            rings, _ = wkb_parts(wkb)
        except Exception:
            skipped += 1
            continue
        ring = max(rings, key=len)          # the outer ring: a hole is not the roofline
        if len(ring) < 8:
            skipped += 1
            continue
        pts = [xy(ring[i], ring[i + 1]) for i in range(0, len(ring) - 2, 2)]   # the last point repeats the first
        cx = sum(p[0] for p in pts) // len(pts)
        cy = sum(p[1] for p in pts) // len(pts)
        if only:
            lon = cx / WORLD * 360 - 180
            s = (0.5 - cy / WORLD) * 2 * math.pi
            lat = math.degrees(math.atan(math.sinh(s)))
            if not (only[0] <= lon <= only[2] and only[1] <= lat <= only[3]):
                skipped += 1
                continue
        buf = tiles.get((cx >> 16, cy >> 16))
        if buf is None:
            buf = tiles[(cx >> 16, cy >> 16)] = array('i')
        buf.extend((len(pts), int(round(h * 10)), 0, 0, pts[0][0], pts[0][1]))
        lx, ly = pts[0]
        for x, y in pts[1:]:
            buf.extend((x - lx, y - ly)); lx, ly = x, y
        kept += 1
    db.executemany('INSERT INTO bldg_osm VALUES (?,?,?,?)',
                   ((x, y, 0, zlib.compress(b.tobytes(), 6)) for (x, y), b in tiles.items()))
    db.execute('INSERT INTO meta VALUES (?,?)', ('bldg_fr', a.departement))
    db.execute('INSERT INTO meta VALUES (?,?)', ('bldg_fr_count', str(kept)))
    db.execute('INSERT INTO meta VALUES (?,?)', ('source', 'BD TOPO 3.0 (IGN)'))
    db.execute('INSERT INTO meta VALUES (?,?)', ('licence', 'Licence Ouverte 2.0 (Etalab)'))
    db.commit()
    db.close()
    tmp.replace(out)
    print(f'{kept:,} bâtiments avec hauteur, {skipped:,} écartés, {len(tiles):,} tuiles z14 '
          f'({time.time() - t0:.0f}s) -> {out}', flush=True)


if __name__ == '__main__':
    main()
