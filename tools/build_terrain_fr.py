#!/usr/bin/env python3
"""Elevation tiles for a French département, from BD ALTI (IGN, Licence Ouverte 2.0).

  derived/buildenv/bin/python tools/build_terrain_fr.py \
      --dir derived/geo/bdalti-972 --departement 972 --out derived/geo/FR-972/terrain.sqlite

IGN ships one 7z per département: 25 m ASCII grids in the département's UTM zone,
heights in the local datum (MART87 for Martinique, GUAD88 for Guadeloupe, REUN89 for
La Réunion). This reads them, converts to WGS84 and writes the same terrain-RGB tiles,
zoom 4-12 and the same encoding, as tools/build_terrain.py — so shaded relief, contour
lines, spot heights and the 3D view work unchanged.

The 25 m grid is finer than a z12 tile's pixels at this latitude, so the resampling is
a bilinear sample of the source, not a resampling of a coarser grid.
"""
import argparse
import math
import sqlite3
import struct
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from pyproj import CRS, Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fsutil import rglob_ci                                              # noqa: E402

def crs_of(src):
    """The delivery's CRS: its .prj when there is one, else the name IGN gives it."""
    prj = next(iter(sorted(rglob_ci(src, '*.prj'))), None)
    if prj:
        return CRS.from_wkt(prj.read_text(encoding='utf-8')).to_epsg() or 4326
    names = ' '.join(p.name.upper() for p in src.rglob('*'))
    for token, epsg in CRS_BY_NAME.items():
        if token in names:
            return epsg
    raise SystemExit('aucun .prj, et aucun CRS reconnaissable dans le nom de la livraison')


HERE = Path(__file__).resolve().parents[1]
# IGN names the CRS in the file name when the delivery carries no .prj. The local datums
# (MART87, REUN89…) differ from WGS84 by about a metre: at 25 m resolution the UTM zone
# of the same number is close enough for a terrain grid.
CRS_BY_NAME = {
    'LAMB93': 2154,
    'WGS84UTM20': 32620, 'WGS84UTM21': 32621, 'WGS84UTM22': 32622,
    'WGS84UTM38S': 32738, 'WGS84UTM39S': 32739, 'WGS84UTM40S': 32740,
    'RGR92UTM40S': 32740, 'RGM04UTM38S': 32738, 'RGFG95UTM22': 32622, 'RGSPM06U21': 32621,
}
MAXZ, SUPERZ, MINZ = 12, 8, 4
SPAN = 2 ** (MAXZ - SUPERZ)
PX = 256 * SPAN
NODATA = -99999.0


def read_asc(path):
    """An ARC/INFO ASCII grid: six header lines, then the rows."""
    with open(path, 'r', encoding='utf-8', errors='replace') as stream:
        head = {}
        # certaines livraisons ont des lignes d'en-tête à trois champs ou des lignes
        # vides : on n'en retient que la clé et la première valeur.
        while len(head) < 6:
            parts = stream.readline().split()
            if len(parts) >= 2:
                head[parts[0].lower()] = float(parts[1])
        data = np.array(stream.read().split(), dtype=np.float32).reshape(int(head['nrows']), int(head['ncols']))
    data[data <= NODATA + 1] = np.nan
    return head, data


def tile_lonlat(z, x, y, n):
    """Pixel-centre longitudes (n,) and latitudes (n,) for an n-px square covering tile z/x/y."""
    t = (np.arange(n) + 0.5) / n
    lon = (x + t) / 2 ** z * 360 - 180
    merc = math.pi * (1 - 2 * (y + t) / 2 ** z)
    lat = np.degrees(np.arctan(np.sinh(merc)))
    return lon, lat


def png(h):
    """256x256 heights (m, NaN = sea level) -> terrain-RGB PNG bytes, as build_terrain.py."""
    v = np.clip(np.round((np.nan_to_num(h, nan=0.0) + 10000) * 10), 0, 2 ** 24 - 1).astype(np.uint32)
    rgb = np.stack([(v >> 16) & 255, (v >> 8) & 255, v & 255], -1).astype(np.uint8).reshape(h.shape[0], -1)
    up = rgb.copy()
    up[1:] = rgb[1:] - rgb[:-1]
    raw = np.hstack([np.full((h.shape[0], 1), 2, np.uint8), up]).tobytes()
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', h.shape[1], h.shape[0], 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def down(h):
    """Halve resolution, ignoring NaN (mean of the available samples)."""
    s = h.reshape(h.shape[0] // 2, 2, h.shape[1] // 2, 2)
    with np.errstate(invalid='ignore'):
        return np.nanmean(s, axis=(1, 3)).astype(np.float32) if np.isnan(s).any() else s.mean(axis=(1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='unzipped BD ALTI 7z directory')
    ap.add_argument('--departement', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default='BD ALTI v2 25 m (IGN)')
    a = ap.parse_args()
    src = Path(a.dir)
    started = time.time()

    grids = [read_asc(p) for p in sorted(rglob_ci(src, '*.asc'))]
    if not grids:
        raise SystemExit(f'no .asc grid in {src}')
    crs = CRS.from_epsg(crs_of(src))
    to_wgs = Transformer.from_crs(crs, 4326, always_xy=True)
    to_utm = Transformer.from_crs(4326, crs, always_xy=True)

    cell = grids[0][0]['cellsize']
    x0 = min(h['xllcorner'] for h, _ in grids)
    y0 = min(h['yllcorner'] for h, _ in grids)
    width = int(round((max(h['xllcorner'] + h['ncols'] * cell for h, _ in grids) - x0) / cell))
    height = int(round((max(h['yllcorner'] + h['nrows'] * cell for h, _ in grids) - y0) / cell))
    dem = np.full((height, width), np.nan, np.float32)
    for head, data in grids:
        col = int(round((head['xllcorner'] - x0) / cell))
        row = int(round((head['yllcorner'] - y0) / cell))
        dem[row:row + data.shape[0], col:col + data.shape[1]] = data[::-1]   # an ASC grid starts at its north edge
    print(f'{len(grids)} grids, {width}x{height} cells of {cell:g} m, {crs.to_epsg() or crs.name}', flush=True)

    # The box, from the four corners of the source extent.
    xs, ys = to_wgs.transform([x0, x0, x0 + width * cell, x0 + width * cell],
                              [y0, y0 + height * cell, y0, y0 + height * cell])
    box = (min(xs), min(ys), max(xs), max(ys))
    print('box', ','.join(f'{v:.3f}' for v in box), flush=True)

    def sample(lon, lat):
        """Bilinear heights (m) on the lon x lat grid; NaN outside the source."""
        x, y = to_utm.transform(lon, lat)
        fr = (y - y0) / cell - 0.5
        fc = (x - x0) / cell - 0.5
        inside = (fc >= -0.5) & (fc <= width - 0.5) & (fr >= -0.5) & (fr <= height - 0.5)
        r0 = np.clip(np.floor(fr).astype(int), 0, height - 2)
        c0 = np.clip(np.floor(fc).astype(int), 0, width - 2)
        wr = np.clip(fr - r0, 0, 1).astype(np.float32)[:, None]
        wc = np.clip(fc - c0, 0, 1).astype(np.float32)[None, :]
        v = (dem[np.ix_(r0, c0)] * (1 - wr) * (1 - wc) + dem[np.ix_(r0 + 1, c0)] * wr * (1 - wc)
             + dem[np.ix_(r0, c0 + 1)] * (1 - wr) * wc + dem[np.ix_(r0 + 1, c0 + 1)] * wr * wc)
        v[~inside] = np.nan
        return v

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.partial')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    n = 2 ** SUPERZ
    x0t, x1t = int((box[0] + 180) / 360 * n), int((box[2] + 180) / 360 * n)
    ys = [int((1 - math.log(math.tan(math.radians(l)) + 1 / math.cos(math.radians(l))) / math.pi) / 2 * n)
          for l in (box[3], box[1])]
    tiles = 0
    low = {}
    for x8 in range(x0t, x1t + 1):
        # y grows southward, so the northern tile has the smaller index
        for y8 in range(min(ys), max(ys) + 1):
            lon, lat = tile_lonlat(SUPERZ, x8, y8, PX)
            h = sample(lon, lat)
            if np.isnan(h).all():
                continue
            for z in range(MAXZ, SUPERZ - 1, -1):
                m = 2 ** (z - SUPERZ)
                for j in range(m):
                    for i in range(m):
                        part = h[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256]
                        if not np.isnan(part).all():
                            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x8 * m + i, y8 * m + j, png(part)))
                            tiles += 1
                if z > SUPERZ:
                    h = down(h)          # z11 samples the same ground at 512 px, and so on
            low[(x8, y8)] = h               # h is now the 256 px heights of the z8 tile
            db.commit()
            print(f'supertile {x8},{y8}: {tiles:,} tiles, {time.time() - started:.0f}s', flush=True)
    # zoom 7..4 from the z8 heights
    level = low
    for z in range(SUPERZ - 1, MINZ - 1, -1):
        nxt = {}
        for (x, y) in {(x // 2, y // 2) for x, y in level}:
            q = np.full((512, 512), np.nan, np.float32)
            for dy in (0, 1):
                for dx in (0, 1):
                    part = level.get((2 * x + dx, 2 * y + dy))
                    if part is not None:
                        q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = part
            h = down(q)
            nxt[(x, y)] = h
            if not np.isnan(h).all():
                db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, png(h)))
                tiles += 1
        level = nxt
    db.commit()
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('country', 'FR'), ('departement', a.departement), ('source', a.source),
        ('crs', str(crs.to_epsg() or crs.name)), ('cell_m', str(cell)), ('grids', str(len(grids))),
        ('licence', 'Licence Ouverte 2.0 (Etalab)'), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
    ])
    db.commit()
    db.close()
    tmp.replace(out)
    print(f'done: {tiles:,} tiles in {time.time() - started:.0f}s -> {out}', flush=True)


if __name__ == '__main__':
    main()
