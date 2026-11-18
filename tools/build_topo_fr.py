#!/usr/bin/env python3
"""Add the names BD TOPO carries to a national map built by tools/build_map_fr.py.

  derived/buildenv/bin/python tools/build_topo_fr.py \
      --dir derived/geo/bdtopo-972 --departement 972 --map derived/geo/FR-972/national.sqlite

IGN's BD TOPO names what OpenStreetMap often leaves unnamed: ponds, reservoirs and
river arms (in Martinique OSM names 5 of 866 water surfaces), and the quartiers and
lieux-dits a map shows as labels. This reads the département's 7z (all themes,
shapefiles), projects to WGS84 and appends rows to the existing national.sqlite in
the same feat/feat_idx schema, so nothing downstream changes.

Rows whose name is already in the map are skipped, so running it after a rebuild does
not duplicate. The source and the licence are recorded in meta.
"""
import argparse
import math
import sqlite3
import struct
import time
from array import array
from pathlib import Path

from pyproj import CRS

HERE = Path(__file__).resolve().parent.parent
Q = 100000
# BD TOPO nature -> the class the map already draws for that kind of ground
PLACE_CLS = {'Quartier': ('suburb', 12), 'Lieu-dit habité': ('village', 13), 'Hameau': ('village', 13)}


def pack(parts):
    """int32 array: nparts, then for each part npts followed by quantized x,y deltas."""
    a = array('i', [len(parts)])
    for p in parts:
        n = len(p) // 2
        a.append(n)
        lx = ly = 0
        for i in range(n):
            x, y = int(round(p[2 * i] * Q)), int(round(p[2 * i + 1] * Q))
            a.append(x - lx)
            a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


def bbox(parts):
    xs = [v for p in parts for v in p[0::2]]
    ys = [v for p in parts for v in p[1::2]]
    return min(xs), max(xs), min(ys), max(ys)


def area_z(minx, maxx, miny, maxy, base):
    size = max(maxx - minx, maxy - miny)
    if size <= 0:
        return 17
    return max(base, min(16, int(math.log2(360 / size)) - 4))


def simplify(flat, tol):
    """Drop points closer than tol (degrees) to the previous kept point; keeps endpoints."""
    if len(flat) <= 4 or tol <= 0:
        return flat
    out = [flat[0], flat[1]]
    px, py = flat[0], flat[1]
    for i in range(2, len(flat) - 2, 2):
        x, y = flat[i], flat[i + 1]
        if abs(x - px) > tol or abs(y - py) > tol:
            out += [x, y]
            px, py = x, y
    out += [flat[-2], flat[-1]]
    return out


def wkb_parts(b, o=0):
    """Return (list of parts as flat [x,y,...] lists, offset). Polygons yield their rings as parts.

    The type is taken modulo 1000, so the ISO Z/M flags (1003, 2006, ...) are handled too.
    """
    le = b[o] == 1
    e = '<' if le else '>'
    t = struct.unpack_from(e + 'I', b, o + 1)[0] % 1000
    o += 5
    if t == 1:
        x, y = struct.unpack_from(e + 'dd', b, o)
        return [[x, y]], o + 16
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
    prj = next(iter(sorted(src.rglob('*.prj'))), None)
    if prj is None:
        raise SystemExit('ni .gpkg ni .prj dans la livraison BD TOPO')
    crs = CRS.from_wkt(prj.read_text(encoding='utf-8'))
    return 'shp', src, crs.to_epsg() or 4326


def rows(con, kind, target, layer, wanted, epsg):
    """Yield (parts, values) for one layer, projected to WGS84.

    A GeoPackage names its layers and columns in lower case and its geometry `geometrie`;
    the wanted columns are matched case-insensitively, so the same call reads both formats.
    """
    name = layer.lower() if kind == 'gpkg' else layer
    geom = 'geometrie' if kind == 'gpkg' else 'geom'
    if kind == 'gpkg':
        describe, args = 'DESCRIBE SELECT * FROM ST_Read(?, layer=?)', [str(target), name]
    else:
        describe, args = 'DESCRIBE SELECT * FROM ST_Read(?)', [str(layer)]
    have = {r[0].lower(): r[0] for r in con.execute(describe, args).fetchall()}
    if any(w.lower() not in have for w in wanted):
        return          # this layer does not carry what we came for (the caller unpacks exactly these)
    cols = [have[w.lower()] for w in wanted]
    select = f"ST_AsWKB(ST_Force2D(ST_Transform({geom}, 'EPSG:{epsg}', 'EPSG:4326')))," + ','.join(cols)
    if kind == 'gpkg':
        sql, args = f'SELECT {select} FROM ST_Read(?, layer=?)', [str(target), name]
    else:
        sql, args = f'SELECT {select} FROM ST_Read(?)', [str(layer)]
    try:
        got = con.execute(sql, args).fetchall()
    except Exception as exc:
        print(f'  {layer}: illisible ({exc})')
        return
    for row in got:
        if row[0] is None:
            continue
        try:
            yield wkb_parts(row[0])[0], row[1:]
        except Exception:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='unzipped BD TOPO 7z directory')
    ap.add_argument('--departement', required=True)
    ap.add_argument('--map', required=True, help='national.sqlite from build_map_fr.py')
    ap.add_argument('--source', default='BD TOPO 3.0 (IGN)')
    ap.add_argument('--box', help='W,S,E,N — limiter à un département quand la livraison est régionale')
    a = ap.parse_args()
    only = tuple(float(v) for v in a.box.split(',')) if a.box else None
    src_dir = Path(a.dir)
    out = Path(a.map)
    if not out.exists():
        raise SystemExit(f'{out} introuvable : construisez d’abord la carte avec build_map_fr.py')

    kind, target, epsg = delivery(src_dir)
    print(f'CRS EPSG:{epsg}, livraison {"GeoPackage" if kind == "gpkg" else "shapefiles"}', flush=True)

    import duckdb
    con = duckdb.connect()
    con.execute('INSTALL spatial; LOAD spatial;')
    con.execute('SET geometry_always_xy = true')   # lon,lat order in and out

    tmp = out.with_suffix('.topo')
    tmp.unlink(missing_ok=True)
    dst = sqlite3.connect(tmp)
    dst.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
      CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    # copy the existing map
    src = sqlite3.connect(f'file:{out}?mode=ro', uri=True)
    for row in src.execute('SELECT id,layer,cls,name,minz,geom FROM feat ORDER BY id'):
        dst.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', row)
    for row in src.execute('SELECT id,minx,maxx,miny,maxy,minz,maxz FROM feat_idx'):
        dst.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', row)
    for k, v in src.execute('SELECT key,value FROM meta'):
        dst.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (k, v))
    if src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='poi'").fetchone():
        cols = [r[1] for r in src.execute('PRAGMA table_info(poi)')]
        dst.execute('CREATE TABLE poi(' + ','.join(cols) + ')')
        dst.executemany('INSERT INTO poi VALUES (' + ','.join('?' * len(cols)) + ')',
                        src.execute('SELECT * FROM poi'))
        dst.execute('CREATE INDEX poi_cls ON poi(cls, lon, lat)')
    fid = [dst.execute('SELECT COALESCE(MAX(id),0) FROM feat').fetchone()[0]]
    known = {r[0] for r in dst.execute('SELECT name FROM feat WHERE name IS NOT NULL')}
    print(f'{fid[0]:,} traits existants, {len(known):,} noms', flush=True)

    def add(layer, cls, name, minz, parts):
        if not parts:
            return 0
        bx = bbox(parts)
        if only and (bx[1] < only[0] or bx[0] > only[2] or bx[3] < only[1] or bx[2] > only[3]):
            return 0
        # a geometry that did not project cleanly is worse than no geometry
        if not (-180 <= bx[0] <= 180 and -180 <= bx[1] <= 180 and -90 <= bx[2] <= 90 and -90 <= bx[3] <= 90):
            return 0
        fid[0] += 1
        dst.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (fid[0], layer, cls, name, minz, pack(parts)))
        dst.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (fid[0], *bx, minz, 30))
        return 1

    def layer(name):
        """The layer to read: a GeoPackage table name, or the first matching shapefile."""
        if kind == 'gpkg':
            return name
        found = sorted(src_dir.rglob(name + '.shp'))
        return found[0] if found else None

    t0 = time.time()
    added = {}
    # water surfaces BD TOPO names and OSM does not
    p = layer('SURFACE_HYDROGRAPHIQUE')
    if p:
        for parts, (nature, nom) in rows(con, kind, target, p, ('NATURE', 'NOM_P_EAU'), epsg):
            nom = (nom or '').strip()
            if not nom or nom in known:
                continue
            known.add(nom)
            added['surfaces d’eau'] = added.get('surfaces d’eau', 0) + add(
                'water', 'lake' if nature in ('Plan d’eau', 'Retenue') else 'river', nom, area_z(*bbox(parts), 7), parts)
    # named river arms
    p = layer('TRONCON_HYDROGRAPHIQUE')
    if p:
        for parts, (nom,) in rows(con, kind, target, p, ('NOM_C_EAU',), epsg):
            nom = (nom or '').strip()
            if not nom or nom in known:
                continue
            known.add(nom)
            added['cours d’eau'] = added.get('cours d’eau', 0) + add('waterway', 'river', nom, 12, [simplify(x, 0.00005) for x in parts])
    # quartiers and lieux-dits, drawn as labels only
    p = layer('ZONE_D_HABITATION')
    if p:
        for parts, (nature, nom) in rows(con, kind, target, p, ('NATURE', 'TOPONYME'), epsg):
            nom = (nom or '').strip()
            cls, minz = PLACE_CLS.get(nature, ('suburb', 14))
            if not nom or nom in known:
                continue
            known.add(nom)
            added['lieux-dits'] = added.get('lieux-dits', 0) + add('place', cls, nom, minz, [simplify(x, 0.00002) for x in parts])

    dst.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('topo', a.source))
    dst.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('topo_licence', 'Licence Ouverte 2.0 (Etalab)'))
    dst.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('topo_crs', str(epsg)))
    dst.commit()
    dst.close()
    src.close()
    tmp.replace(out)
    total = sum(added.values())
    print(f'ajouté : ' + ', '.join(f'{v:,} {k}' for k, v in added.items()) + f' — {fid[0]:,} traits en {time.time() - t0:.0f}s', flush=True)
    print(f'total {total:,} -> {out}', flush=True)


if __name__ == '__main__':
    main()
