#!/usr/bin/env python3
"""Perennial food crops from the RPG (Registre Parcellaire Graphique, IGN/ASP).

  derived/buildenv/bin/python tools/build_crops_fr.py \
      --dir derived/geo/rpg-r94 --departement 94 --box 7.2,41.3,7.7,41.9 \
      --out derived/geo/crops.sqlite

The RPG is published one GeoPackage per region, four of them: Parcelles (the declared
parcels, with the crop code), Ilots, ZDH and SNA. Only Parcelles carries the culture.

Writes the same crops.sqlite as tools/build_crops.py: `resource` + `spatial` for the
clickable cells the map lists, and `tile` (RGBA PNG, zoom 7-13) for the colour overlay.

The RPG has no code for every fruit. What is mapped, by the official code_group:
  21        vineyards          (VRC, vines)
  20, 23    orchards           (vergers, agrumes, oliviers)
  and by code_cultu: FRA, FLA, FLP as berries.
Everything else — cereals, oilseeds, vegetables, grass — is left out: it is not a
perennial food crop the map's layers are about.
"""
import argparse
import json
import math
import sqlite3
import struct
import time
import zlib
from array import array
from pathlib import Path

import numpy as np

MAXZ, MINZ = 13, 7
# kind -> RGBA, and the index in the overlay palette
KINDS = {'vineyard': (120, 50, 150), 'orchard': (90, 150, 70), 'berries': (60, 70, 180)}
BERRY = {'FRA', 'FLA', 'FLP'}
GROUP_KIND = {21: 'vineyard', 20: 'orchard', 23: 'orchard'}


def kind_of(group, code):
    k = GROUP_KIND.get(int(group)) if group not in (None, '') else None
    if k:
        return k
    return 'berries' if (code or '').upper() in BERRY else None


def gpkg_wkb(b):
    """Strip a GeoPackageBinary header ('GP', flags, srs_id, envelope) back to WKB."""
    if b[:2] != b'GP':
        return b
    n = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}.get((b[3] >> 1) & 0x07, 0)
    return b[8 + 8 * n:]


def wkb_parts(b, o=0):
    """(list of flat [x,y,...] rings, offset); the type is read modulo 1000 for Z/M flags."""
    le = b[o] == 1
    e = '<' if le else '>'
    t = struct.unpack_from(e + 'I', b, o + 1)[0] % 1000
    o += 5
    if t == 1:
        return [[struct.unpack_from(e + 'dd', b, o)[0]]], o + 16
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


def png_rgba(rgba):
    raw = np.hstack([np.zeros((rgba.shape[0], 1), np.uint8), rgba.reshape(rgba.shape[0], -1)]).tobytes()
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', rgba.shape[1], rgba.shape[0], 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def down(q):
    """2x downsample of class indices: the strongest crop present wins."""
    s = np.stack([q[0::2, 0::2], q[0::2, 1::2], q[1::2, 0::2], q[1::2, 1::2]])
    out = s.max(axis=0)
    for i in range(4):
        out = np.where((s[i] > 0) & ((s == s[i]).sum(axis=0) >= 2), s[i], out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='unzipped RPG delivery directory')
    ap.add_argument('--departement', required=True)
    ap.add_argument('--box', help='W,S,E,N — the département, inside the region')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    src = Path(a.dir)
    only = tuple(float(v) for v in a.box.split(',')) if a.box else None
    parcels = next(iter(sorted(src.rglob('RPG_Parcelles.gpkg'))), None)
    if not parcels:
        raise SystemExit(f'pas de RPG_Parcelles.gpkg dans {src}')
    db = sqlite3.connect(f'file:{parcels}?mode=ro', uri=True)
    srs = db.execute('SELECT srs_id FROM gpkg_contents LIMIT 1').fetchone()[0]
    rows = db.execute('SELECT geom, code_group, code_cultu, surf_parc FROM RPG_Parcelles').fetchall()
    db.close()

    from pyproj import CRS, Transformer
    to_wgs = Transformer.from_crs(CRS.from_epsg(int(srs)), 4326, always_xy=True)

    keep = []
    for wkb, group, code, surf in rows:
        k = kind_of(group, code)
        if not k:
            continue
        try:
            rings, _ = wkb_parts(gpkg_wkb(wkb))
        except Exception:
            continue
        ring = max(rings, key=len)
        lon, lat = to_wgs.transform([ring[i] for i in range(0, len(ring) - 2, 2)],
                                    [ring[i + 1] for i in range(0, len(ring) - 2, 2)])
        lon = np.asarray(lon); lat = np.asarray(lat)
        w, s, e, n = lon.min(), lat.min(), lon.max(), lat.max()
        if only and (e < only[0] or w > only[2] or n < only[1] or s > only[3]):
            continue
        keep.append((k, list(zip(lon.tolist(), lat.tolist())), float(surf or 0)))
    print(f'{len(keep):,} parcelles retenues', flush=True)
    if not keep:
        raise SystemExit('aucune parcelle de culture pérenne dans cette boîte')

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.partial')
    tmp.unlink(missing_ok=True)
    dst = sqlite3.connect(tmp)
    dst.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT);
      CREATE INDEX resource_kind ON resource(kind);
      CREATE VIRTUAL TABLE spatial USING rtree(id, minx, maxx, miny, maxy);
      CREATE TABLE tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    palette = np.zeros((len(KINDS) + 1, 4), np.uint8)
    for i, k in enumerate(KINDS, 1):
        palette[i] = (*KINDS[k], 190)
    idx = {k: i for i, k in enumerate(KINDS, 1)}
    # clickable cells, and the z13 classes of every tile a parcel touches
    tiles = {}
    nz = 2 ** MAXZ
    t = (np.arange(256) + .5) / 256
    for kind, pts, surf in keep:
        lon = np.array([p[0] for p in pts]); lat = np.array([p[1] for p in pts])
        cx, cy = float(np.mean(lon)), float(np.mean(lat))
        cur = dst.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source) VALUES (?,?,?,?,?,?,?)',
                          (f'{a.departement}:{len(keep)}', kind,
                           {'vineyard': 'Vignoble', 'orchard': 'Verger', 'berries': 'Culture de petits fruits'}[kind],
                           cy, cx, json.dumps({'crop_ha': surf, 'departement': a.departement}),
                           'RPG 4.0 (IGN / ASP), Licence Ouverte 2.0'))
        dst.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, cx, cx, cy, cy))
        tx = int((cx + 180) / 360 * nz); ty = int((1 - math.log(math.tan(math.radians(cy)) + 1 / math.cos(math.radians(cy))) / math.pi) / 2 * nz)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                gx, gy = tx + dx, ty + dy
                lo = (gx + t) / nz * 360 - 180
                la = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (gy + t) / nz))))
                LO, LA = np.meshgrid(lo, la)
                inside = np.zeros((256, 256), bool)
                with np.errstate(invalid='ignore', divide='ignore'):
                    for i in range(len(lon)):
                        j = (i + 1) % len(lon)
                        cross = (lat[i] > LA) != (lat[j] > LA)
                        xin = (lon[j] - lon[i]) * (LA - lat[i]) / (lat[j] - lat[i]) + lon[i]
                        inside ^= cross & (LO < xin)
                if inside.any():
                    v = tiles.setdefault((gx, gy), np.zeros((256, 256), np.uint8))
                    v[inside] = idx[kind]
    dst.commit()
    level = tiles
    for z in range(MAXZ, MINZ - 1, -1):
        for (x, y), v in level.items():
            dst.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, png_rgba(palette[v])))
        if z > MINZ:
            nxt = {}
            for (x, y) in {(x // 2, y // 2) for x, y in level}:
                q = np.zeros((512, 512), np.uint8)
                for dy in (0, 1):
                    for dx in (0, 1):
                        v = level.get((2 * x + dx, 2 * y + dy))
                        if v is not None:
                            q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = v
                nxt[(x, y)] = down(q)
            level = nxt
        dst.commit()
    dst.execute('INSERT INTO meta VALUES (?,?)', ('built', json.dumps(
        {'parcelles': len(keep), 'departement': a.departement, 'tiles': len(tiles),
         'at': time.strftime('%Y-%m-%dT%H:%M:%S')})))
    dst.commit()
    dst.close()
    tmp.replace(out)
    print(f'{len(tiles):,} tuiles z13 -> {out}', flush=True)


if __name__ == '__main__':
    main()
