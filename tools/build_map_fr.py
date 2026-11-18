#!/usr/bin/env python3
"""Convert a département's Geofabrik shapefiles (OpenStreetMap, ODbL) into the
`national.sqlite` the app draws: the same feat/feat_idx/poi/meta schema as
tools/build_map.py, which reads the GeoPackage Geofabrik publishes for metropolitan
regions. The overseas départements have no GeoPackage, so the shapefile set is the
source there — and it is the same data either way.

  derived/buildenv/bin/python tools/build_map_fr.py \
      --shp derived/geo/martinique-latest-free.shp --departement 972 \
      --out derived/geo/FR-972/national.sqlite

Input is an unzipped `martinique-latest-free.shp.zip`. Output tables:
  feat(id, layer, cls, name, minz, geom)   geom = packed int32 lon/lat * 1e6 (see pack())
  feat_idx (R*Tree on bbox)
  poi(id, cls, name, lon, lat)             help-relevant points (hospitals, pharmacies, water...)
  meta(key, value)
"""
import argparse
import math
import sqlite3
import struct
import sys
import time
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from engine.departements import DEPARTEMENT_REGION  # noqa: E402
from engine.regions import REGION_BOXES  # noqa: E402

Q = 1e6
ROAD_Z = {'motorway': 5, 'trunk': 6, 'motorway_link': 10, 'trunk_link': 10, 'primary': 8, 'primary_link': 12,
          'secondary': 10, 'secondary_link': 13, 'tertiary': 11, 'tertiary_link': 13, 'residential': 13,
          'unclassified': 13, 'living_street': 14, 'pedestrian': 14, 'busway': 14, 'service': 15,
          'track': 13, 'track_grade1': 13, 'track_grade2': 13, 'track_grade3': 13, 'track_grade4': 13, 'track_grade5': 13,
          'footway': 15, 'path': 14, 'cycleway': 14, 'steps': 16, 'bridleway': 14, 'unknown': 15}
LANDUSE_KEEP = {'park': 'park', 'forest': 'green', 'grass': 'green', 'meadow': 'green', 'scrub': 'green', 'heath': 'green',
                'recreation_ground': 'park', 'cemetery': 'park', 'allotments': 'farm', 'farmland': 'farm',
                'orchard': 'farm', 'vineyard': 'farm', 'farmyard': 'farm', 'residential': 'res', 'commercial': 'com',
                'retail': 'com', 'industrial': 'ind', 'military': 'ind', 'quarry': 'ind', 'landfill': 'ind'}
PLACE_Z = {'county': 7, 'city': 6, 'town': 9, 'suburb': 12, 'village': 11, 'hamlet': 14, 'locality': 14, 'island': 11,
           'farm': 15, 'region': 5}
POI_KEEP = {'hospital', 'clinic', 'doctors', 'pharmacy', 'chemist', 'dentist', 'veterinary', 'fire_station', 'police',
            'drinking_water', 'water_tower', 'water_works', 'fountain', 'toilet', 'shelter', 'community_centre',
            'town_hall', 'school', 'library', 'supermarket', 'convenience', 'doityourself', 'hardware', 'garden_centre',
            'post_office', 'camp_site', 'wastewater_plant', 'comms_tower', 'spring', 'park', 'courthouse', 'embassy',
            'nursing_home', 'kindergarten', 'college', 'university', 'bicycle_shop', 'car_repair', 'fuel', 'beach'}


def wkb_parts(b, o):
    """Return (list of parts as flat [x,y,...] lists, offset). Polygons yield their rings as parts."""
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
    z = int(math.log2(360 / size)) - 4
    return max(base, min(16, z))


def layer_rows(con, source, name, cols):
    """Yield (parts, values) for one Geofabrik layer, reading WKB through duckdb spatial.

    source is ('shp', directory) or ('gpkg', file): Geofabrik now publishes France's
    regions as GeoPackage and the DROM as shapefiles, and both carry the same
    gis_osm_<name>_free_1 layers.
    """
    cols_sql = ','.join(cols)
    if source[0] == 'shp':
        sql = f'SELECT ST_AsWKB(geom),{cols_sql} FROM ST_Read(?)'
        args = [str(Path(source[1]) / f'gis_osm_{name}_free_1.shp')]
    else:
        sql = f'SELECT ST_AsWKB(geom),{cols_sql} FROM ST_Read(?, layer=?)'
        args = [str(source[1]), f'gis_osm_{name}_free']
    try:
        rows = con.execute(sql, args).fetchall()
    except Exception:
        return
    for row in rows:
        if row[0] is None:
            continue
        try:
            yield wkb_parts(row[0], 0)[0], row[1:]
        except Exception:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shp', help='unzipped Geofabrik *-latest-free.shp directory (DROM)')
    ap.add_argument('--gpkg', help='Geofabrik *-latest-free.gpkg (France’s regions)')
    ap.add_argument('--departement', required=True)
    ap.add_argument('--out', required=True, help='national.sqlite to write')
    ap.add_argument('--source', default='© OpenStreetMap contributors, via Geofabrik (ODbL 1.0)')
    ap.add_argument('--box', help='W,S,E,N; the département region box if omitted')
    a = ap.parse_args()
    if not a.shp and not a.gpkg:
        raise SystemExit('il faut --shp (DROM) ou --gpkg (régions France)')
    source = ('shp', a.shp) if a.shp else ('gpkg', a.gpkg)
    out = Path(a.out)
    if a.box:
        box = tuple(float(v) for v in a.box.split(','))
    else:
        box = REGION_BOXES[DEPARTEMENT_REGION[a.departement]]
    margin = 0.05
    keep = (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.partial')
    tmp.unlink(missing_ok=True)

    import duckdb
    con = duckdb.connect()
    con.execute('INSTALL spatial; LOAD spatial;')

    dst = sqlite3.connect(tmp)
    dst.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
      CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    fid = [0]

    def add(layer, cls, name, minz, parts):
        if not parts:
            return
        bx = bbox(parts)
        # Geofabrik's landuse and water layers carry polygons far outside the extract
        # (a relation clipped to the Caribbean). Keep only what touches the département.
        if bx[1] < keep[0] or bx[0] > keep[2] or bx[3] < keep[1] or bx[2] > keep[3]:
            return
        fid[0] += 1
        dst.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (fid[0], layer, cls, name, minz, pack(parts)))
        dst.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (fid[0], *bx, minz, 30))

    t0 = time.time()
    for parts, (cls, name) in layer_rows(con, source,'water_a', ('fclass', 'name')):
        layer = 'wet' if cls.startswith('wetland') else 'water'
        add(layer, cls, name, area_z(*bbox(parts), 7), [simplify(p, 0.00001) for p in parts])
    for parts, (cls, name) in layer_rows(con, source,'natural_a', ('fclass', 'name')):
        if cls == 'beach':
            add('beach', cls, name, area_z(*bbox(parts), 10), parts)
    for parts, (cls, name) in layer_rows(con, source,'landuse_a', ('fclass', 'name')):
        k = LANDUSE_KEEP.get(cls)
        if k:
            add('land', k, name, area_z(*bbox(parts), 9), [simplify(p, 0.00001) for p in parts])
    dst.commit()
    print('water/land', fid[0], round(time.time() - t0), flush=True)
    for parts, (cls, name) in layer_rows(con, source,'waterways', ('fclass', 'name')):
        add('waterway', cls, name, 10 if cls == 'river' else 13, parts)
    for parts, (cls, name) in layer_rows(con, source,'railways', ('fclass', 'name')):
        add('rail', cls, name, 10 if cls == 'rail' else 13, parts)
    for parts, (cls, name, ref) in layer_rows(con, source,'roads', ('fclass', 'name', 'ref')):
        add('road', cls, name or ref, ROAD_Z.get(cls, 15), parts)
    dst.commit()
    print('roads', fid[0], round(time.time() - t0), flush=True)
    for parts, (cls,) in layer_rows(con, source,'buildings_a', ('fclass',)):
        add('bldg', cls or '', None, 15, [simplify(parts[0], 0.000002)])
    dst.commit()
    print('buildings', fid[0], round(time.time() - t0), flush=True)
    for parts, (cls, pop, name) in layer_rows(con, source,'places', ('fclass', 'population', 'name')):
        if name:
            z = PLACE_Z.get(cls, 14)
            if cls in ('city', 'town') and pop and int(pop) > 300000:
                z = 5
            add('place', cls, name, z, parts)
    pid = 0
    for name, only in (('pois', None), ('pois_a', None), ('natural', {'spring'}), ('natural_a', None)):
        for parts, (cls, pname) in layer_rows(con, source,name, ('fclass', 'name')):
            if cls not in POI_KEEP or (only is not None and cls not in only):
                continue
            minx, maxx, miny, maxy = bbox(parts)
            lon, lat = (minx + maxx) / 2, (miny + maxy) / 2
            if not (keep[0] <= lon <= keep[2] and keep[1] <= lat <= keep[3]):
                continue
            pid += 1
            dst.execute('INSERT INTO poi VALUES (?,?,?,?,?)', (pid, cls, pname, lon, lat))
    dst.execute('CREATE INDEX poi_cls ON poi(cls, lon, lat)')
    dst.executemany('INSERT INTO meta VALUES (?,?)', [
        ('country', 'FR'), ('departement', a.departement),
        ('source', a.source),
        ('bounds', ','.join(f'{v:.2f}' for v in box)),
        ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
    ])
    dst.commit()
    dst.close()
    tmp.replace(out)
    print(f'done: {fid[0]:,} features, {pid:,} pois, {round(time.time() - t0)}s -> {out}', flush=True)


if __name__ == '__main__':
    main()
