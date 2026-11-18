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
    a = ap.parse_args()
    src = Path(a.dir)
    shp = sorted(src.rglob('BATI/BATIMENT.shp'))
    if not shp:
        raise SystemExit(f'pas de BATI/BATIMENT.shp dans {src}')
    prj = sorted(src.rglob('*.prj'))[0]
    epsg = CRS.from_wkt(prj.read_text(encoding='utf-8')).to_epsg() or 4326

    import duckdb
    con = duckdb.connect()
    con.execute('INSTALL spatial; LOAD spatial;')
    con.execute('SET geometry_always_xy = true')
    select = ("ST_AsWKB(ST_Force2D(ST_Transform(geom, 'EPSG:%s', 'EPSG:4326'))), HAUTEUR" % epsg)
    rows = con.execute(f'SELECT {select} FROM ST_Read(?) WHERE HAUTEUR IS NOT NULL', [str(shp[0])]).fetchall()

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
